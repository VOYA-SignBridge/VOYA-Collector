# PHỤ LỤC E: GIAO THỨC ĐO VÀ QUYẾT ĐỊNH KIẾN TRÚC

*Phụ lục này chứa hai loại tạo tác phương pháp: giao thức đầy đủ của bốn phép đo
ở Chương 4, và các biên bản quyết định kiến trúc kèm trạng thái hiện tại của
chúng. Cả hai đều là thứ người phản biện cần tra được, nhưng không cần đọc để
hiểu lập luận của thân bài.*

---

# PHẦN I — GIAO THỨC ĐO

## 1. Năm quy tắc chung, áp cho mọi phép đo

**Quy tắc 1 — Phép đo phải có khả năng thất bại.** Trước khi chạy, phải trả lời
được: *nếu thuộc tính này không đúng, phép đo sẽ trông khác thế nào?* Không trả
lời được thì phép đo không đo gì cả.

**Quy tắc 2 — Đối chứng dương là điều kiện tiên quyết.** Phải chứng minh dụng cụ
đang chạm đúng đối tượng: chủ sở hữu **làm được** thứ mà bên kia không làm được.
Và đối chứng dương phải phủ **cả vế ghi**, không chỉ vế đọc — nếu tài khoản thử
vốn không ghi được gì, thì "không ghi được của bên kia" không nói lên điều gì.

**Quy tắc 3 — Phép đo gắn với một phiên bản mã xác định.** Cây mã được đóng băng
trước khi đo. Mọi thay đổi mã trong lúc đo làm lượt đo đó mất hiệu lực.

> **Quy tắc 3 có một vế thứ hai, và nó đã bị bỏ sót một lần.** Không đủ để phiên
> bản mã *tồn tại*; **artefact phải tự ghi lại phiên bản đó**. Artefact ngày
> 16/08 ghi `git_commit: null` — phiên bản chỉ còn truy được nhờ thẻ của ảnh
> container, một chỗ nằm ngoài artefact và có thể bị ghi đè bất cứ lúc nào.
>
> **Đã vá 17/08/2026.** Danh tính chuẩn nay là **`tree_sha256` của ảnh chụp mã**,
> không phải trạng thái git: ảnh chụp được gắn chỉ-đọc đè lên mã của container
> nên bất biến theo cấu trúc, và nó phủ đúng những tệp tham gia hành vi. Cờ công
> bố nhận một trong hai bằng chứng — ảnh chụp, hoặc một commit sạch cho trường
> hợp đo mã nung sẵn trong ảnh.
>
> Bản đầu của cổng ấy khoá theo `git status` và **chặn nhầm** một lượt đo hợp lệ
> vì một tệp markdown chưa theo dõi. Một cổng chặn nhầm là một cổng sẽ bị tắt.

**Quy tắc 4 — Phát hiện trong lúc đo thì ghi lại, không sửa ngay.** Nếu phép đo
lộ ra một lỗi, đó là **phát hiện của phép đo**. Sửa rồi đo lại trong cùng một
lượt sẽ làm mất bằng chứng và làm kết quả không quy về phiên bản mã nào.

**Quy tắc 5 — Môi trường đo tách khỏi môi trường thí nghiệm.** Hai phép đo đặt hệ
thống ở hai trạng thái khác nhau thì phải chạy ở hai container khác nhau. Dùng
chung sẽ **dịch chuyển cả phân bố** trong khi bảng kết quả vẫn trông bình thường.

**Quy tắc phát biểu kết quả** (bổ sung, áp lúc viết):

* Giới hạn tuyên bố đúng phạm vi bằng chứng.
* Tách **"phép đo hợp lệ"** khỏi **"thuộc tính đạt"**.
* Trình bày kèm **cỡ mẫu, khoảng phân bố và giao thức**.
* Tiêu chí đưa vào phải nêu **trước**, không giải thích **sau**.
* Phân biệt *chưa quan sát thấy vi phạm* với *có cơ chế ngăn vi phạm*.

---

## 2. Giao thức đo cách ly xuyên kho (Trục T2)

### 2.1 Ba nhóm đối kháng và một nhóm đối chứng

| Nhóm | Cấu hình | Câu hỏi | Đi vào chỉ số nào |
|---|---|---|---|
| **Đối chứng** | Chủ sở hữu, đúng quyền, đúng tổ chức | Dụng cụ có chạm được đối tượng không? | Không — là điều kiện tiên quyết |
| **A** | Đúng tổ chức, **sai quyền** | Cổng phân quyền có giữ không? | Tỉ lệ thao tác trái quyền lọt |
| **B** | Đúng quyền, **sai tổ chức** | Ranh giới tổ chức có giữ không? | Tỉ lệ vi phạm xuyên tổ chức |
| **C** | Sai quyền **và** sai tổ chức | Hai cổng cùng lúc | Cả hai chỉ số |

**Nhóm A không được gộp vào chỉ số xuyên tổ chức.** Nó nhắm vào tài nguyên của
chính tổ chức mình, nên theo định nghĩa không thể là vi phạm xuyên tổ chức. Gộp
lại làm chính cái tên của chỉ số nói sai.

### 2.2 Điều kiện tiên quyết — phải đạt đủ trước khi lượt đo được tính

```
1. Fixture gieo NHẤT QUÁN trên CẢ HAI mặt phẳng lưu trữ
      cơ sở dữ liệu ✔  và  hệ tệp ✔
2. Đối chứng dương đạt ĐỦ BỐN thao tác
      đọc danh tính của chính mình      ✔
      đọc phiên thu của tổ chức mình    ✔
      đọc dữ liệu mẫu của chính mình    ✔
      XOÁ mẫu của chính mình            ✔  ← vế ghi, bắt buộc
3. Vai chạy: KHÔNG siêu người dùng, KHÔNG quyền vượt chính sách
4. Cây mã đã đóng băng, ghi lại định danh phiên bản
5. Container đo RIÊNG, không dùng chung với phép đo khác
```

**Điều kiện 1 là blocker đã từng chặn phép đo này.** Lượt đo ngày 15/08/2026 bị
loại vì không tồn tại bước nào tạo ra cùng một fixture logic trên cả hai mặt
phẳng: một kịch bản gieo ghi tệp, một kịch bản khác ghi cơ sở dữ liệu, không bộ
nào phủ cả hai. Đường đọc lớp và mẫu không thuần cơ sở dữ liệu, nên tài khoản thử
nhận mã 404 cho tài nguyên của **chính nó**.

### 2.3 Bốn lớp bằng chứng — thiếu lớp nào thì kết luận sai thế nào

| Lớp | Nội dung | Nếu thiếu, con số 0 tương thích với |
|---|---|---|
| 1. Đối chứng dương | Chủ sở hữu làm được, cả đọc lẫn ghi | Một hệ thống mà **không ai làm được gì** |
| 2. Đối kháng | Ba nhóm A, B, C | Không có dữ liệu để tính tỉ lệ |
| 3. Hậu điều kiện | Dữ liệu bên bị nhắm **vẫn nguyên vẹn** sau lượt đo, trên cả hai mặt phẳng | Một hệ thống trả mã từ chối **nhưng vẫn thực hiện** thao tác |
| 4. Không có ca mờ | Mọi lượt gọi quy được về "chặn" hoặc "vi phạm" | Một hệ thống hỏng, trả mã lỗi máy chủ, bị đếm nhầm thành "đã chặn" |

Lớp 3 là lớp hay bị bỏ sót nhất. Một điểm cuối trả mã 403 rồi vẫn xoá dữ liệu ở
phía sau là chuyện có thật trong các hệ thống có nhiều đường ghi.

### 2.4 Ranh giới của artefact

Artefact ghi thẳng các ranh giới sau, để nếu phép đo đạt thì bằng chứng vẫn hoàn
toàn hợp lệ **trong phạm vi đã tuyên bố**:

| Ranh giới | Nội dung |
|---|---|
| Quy mô | **Hai** tổ chức, không phải quy mô lớn |
| Phạm vi tài nguyên | Chỉ các tài nguyên **có bề mặt API** — hai cấp phạm vi dưới không có gì để đo |
| Bản chất | **Đối kháng**, không phải chứng minh hình thức |
| Môi trường | **Không** phải cơ sở dữ liệu sản xuất — bộ thử cố ý phát lệnh xoá thật |

### 2.5 Vì sao thí nghiệm không chạy trên dữ liệu sản xuất

Bộ thử cố tình phát lệnh **xoá** tổ chức, **xoá** mẫu và **xoá** lớp. Cả ba phải
bị chặn — và phép đo tồn tại chính vì điều đó **chưa được chứng minh**. Nếu cách
ly thủng, phép đo sẽ chứng minh bằng cách xoá thật.

---

## 3. Giao thức đo độ trễ (Trục T3a)

```
Khởi động    50 lượt / điểm cuối / lượt chạy — KHÔNG tính vào thống kê
Đo           1.000 lượt / điểm cuối / lượt chạy
Đồng thời    1
Lặp lại      3 lượt chạy độc lập
Gộp          trung vị của BA giá trị phân vị — KHÔNG gộp 3.000 mẫu
```

**Vì sao không gộp 3.000 mẫu.** Nếu lượt thứ hai chậm gấp đôi vì máy bận việc
khác, tổng mẫu vẫn cho một con số trông hợp lý và không ai biết. Ba giá trị đặt
cạnh nhau thì bất thường tự lộ, còn trung vị thì không bị một lượt hỏng kéo đi.

**Ngưỡng công bố phân vị** — một phân vị chỉ có nghĩa khi đuôi của nó có đủ quan
sát đứng sau; yêu cầu tối thiểu **5 quan sát trong đuôi**:

| Phân vị | Đuôi | Cần ít nhất |
|---|---|---|
| p95 | 5 % | 100 lượt phục vụ |
| p99 | 1 % | 500 lượt phục vụ |

Thiếu thì **để trống, không in**. Với n = 1.000 thì p99 tựa trên 10 quan sát cuối.

**Cấu hình môi trường đo:**

| | |
|---|---|
| Container | **Riêng**, không phải container của phép đo cách ly |
| Ảnh ứng dụng | Cùng ảnh với sản xuất |
| Cơ sở dữ liệu | Cơ sở dữ liệu kiểm thử |
| Cây dữ liệu | **Rỗng**, do container tự tạo, không gắn fixture nào |
| Kết nối | Giữ sống, một kết nối cho cả lượt chạy |
| Vai chạy | Vai kiểm thử — **không** siêu người dùng, **không** quyền vượt chính sách |
| Giới hạn tần suất | Trần đã nâng — **là cấu hình của môi trường đo**, phải nói rõ |
| Tài khoản | Vai **thường**, tổ chức mặc định |

**Giới hạn bắt buộc nêu kèm.** Đồng thời = 1 nghĩa là đây là **độ trễ cơ sở**: nó
trả lời "một yêu cầu tốn bao lâu khi không có ai tranh chấp", **không** trả lời
"hệ thống chịu được bao nhiêu yêu cầu mỗi giây", và **không** chứng minh cách ly
hiệu năng giữa các tổ chức. Không có hệ số quy đổi nào giữa các cấu hình khác nhau.

---

## 4. Giao thức đo hiệu quả lưu trữ (Trục T3b)

### 4.1 Vì sao phải đo trên nguồn ngoài

Kho dữ liệu có **8.784 tệp đặc trưng và 0 tệp video**. Nguyên nhân là thiết kế:
trình duyệt trích điểm mốc tại máy người dùng và chỉ gửi lên mảng số; video thô
chưa bao giờ rời khỏi trình duyệt.

Đây **không phải thiếu sót của phép đo — nó là hệ quả trực tiếp của thiết kế**.
Chính cơ chế tạo ra hiệu quả lưu trữ cũng là cơ chế làm mất vật đối chứng.

Hai chi tiết phải ghi để không ai đo nhầm:

* Thư mục mang tên "raw" **không** chứa video — nó chứa kho điểm mốc trước chuẩn
  hoá.
* Sổ ghi các lượt tải video **chỉ có dòng tiêu đề**, và không có cột kích thước;
  kể cả nếu đã từng có lượt tải thì kích thước gốc cũng không lưu lại.

### 4.2 Ghép cặp và tiêu chí loại

```
Nguồn video    : bộ clip từ điển bên ngoài
Ghép cặp       : theo lớp từ vựng
Điều kiện giữ  : thời lượng clip khớp cửa sổ thu của mẫu
Cỡ mẫu cuối    : 54 cặp
Báo cáo        : tỉ lệ giảm trên TỔNG và trên TRUNG VỊ, kèm khoảng p5–p95
```

**Ba nguồn đối chứng đã bị loại, và lý do loại là phần đáng giữ:**

| Nguồn bị loại | Con số nó cho | Vì sao loại |
|---|---|---|
| Cặp không khớp thời lượng | 97,6 % | Hưởng lợi từ việc so với clip **dài hơn** |
| Cặp có mẫu trích xuất thất bại | 95,5 % | Tệp nhỏ vì **trích hỏng**, không phải vì nén tốt |
| Sáu tệp xem trước do nền tảng sinh | — | Trung vị **28,9 KiB**, nhỏ hơn cả trung vị tệp đặc trưng; dùng làm mốc "video thô" cho kết luận **ngược hẳn** |

**Tiêu chí loại được nêu trước khi đo**, đúng theo quy tắc 4 ở §1. Nếu nêu sau,
việc chọn 92,2 % thay vì 97,6 % sẽ trông như chọn con số thuận tiện.

### 4.3 Tham số để tái lập

| Tham số | Giá trị |
|---|---|
| Số khung mục tiêu | 60 |
| Chiều mỗi khung | 126 = 21 điểm mốc × 3 toạ độ × 2 bàn tay |
| Chiều rộng khung hình khi thu | 1280 |
| Định dạng lưu | Mảng số nhiều chiều **có nén** |

**Giới hạn bắt buộc nêu kèm:** nguồn video ghép cặp là bản quay **đã nén để phân
phối trên web**, không phải luồng thu của chính hệ thống. Không được phát biểu
con số này như đo trên dữ liệu do nền tảng thu.

---

## 5. Giao thức đo toàn vẹn nguồn sự thật (Trục T4)

### 5.1 Điều kiện then chốt

Phép đo chạy qua **đúng đường tiêu thụ của ứng dụng**, không qua hàm trợ giúp.
Điều kiện này không phải chi tiết kỹ thuật: lỗi đã từng xảy ra **chính ở chỗ phép
kiểm không phủ hết thứ nó bảo vệ** — danh sách cột bắt buộc thiếu sáu cột, khiến
một bản công bố có lược đồ thiếu vẫn qua được khâu xác minh rồi mới hỏng giữa
chừng lúc nhập.

### 5.2 Chín kịch bản và thuộc tính mỗi kịch bản kiểm

| Ca | Thao tác giả mạo | Vế hợp đồng được kiểm |
|---|---|---|
| S1 | Không giả mạo | Đường thuận — phải chấp nhận |
| S2 | Đổi **một byte** trong tạo tác sau khi ký | Toàn vẹn |
| S3 | Sửa mã băm trong bản kê, giữ chữ ký cũ | Toàn vẹn của chính bản kê |
| S4 | Ký hợp lệ bằng khoá **không được tin cậy** | **Xác thực nguồn** |
| S5 | Chữ ký hỏng | Chữ ký hợp lệ |
| S6 | Thiếu chữ ký khi chính sách đòi ký | Chính sách bắt buộc ký |
| S7 | **Lùi số hiệu phiên bản** | **Chính sách phiên bản** |
| S8 | Phiên bản mới, nguồn tin cậy | Đường thuận thứ hai |
| S9 | Công bố chỉ bổ sung | Nguyên tắc chỉ-điền-không-xoá |

**Hợp đồng bốn vế:**

```
Tạo tác hợp lệ = Toàn vẹn ∧ Chữ ký hợp lệ ∧ Người ký được tin cậy ∧ Chính sách phiên bản hợp lệ
```

**S4 là ca quan trọng nhất, và hay bị bỏ sót nhất.** Kẻ tấn công dựng được một bộ
dữ liệu khác, tính mã băm đúng, viết bản kê đúng, rồi tự ký bằng khoá **của
hắn** — chữ ký ấy hợp lệ về mật mã. Nếu hệ thống chỉ hỏi "chữ ký có hợp lệ không"
mà không hỏi "hợp lệ theo khoá **nào**" thì toàn vẹn đúng nhưng thẩm quyền sai.
S4 đo vế thứ ba, và **đạt**.

**S7 nằm ngoài ma trận tham số.** Hợp đồng ở đây có hai vế không giống nhau: (a)
hệ có **từ chối** lùi phiên bản không, và (b) nếu chấp nhận, việc lùi có **phá
huỷ** trạng thái mới hơn không. Đo được vế (b) đòi **hai lượt đồng bộ thật** —
phải có phiên bản mới đã vào cơ sở dữ liệu rồi mới biết nó mất hay còn. Nên ca
này phải chạy riêng.

### 5.3 Cách đọc kết quả

```
9/9  kịch bản THỰC THI và cho kết quả xác định   ← phép đo hợp lệ
8    thoả thuộc tính mong đợi                     ← thuộc tính đạt
1    phát hiện GIỚI HẠN THẬT (S7)                 ← phần đáng giá nhất
```

**Không được viết "9/9 đạt".** Đây là ví dụ điển hình của việc gộp "phép đo hợp
lệ" với "thuộc tính đạt".

---

# PHẦN II — BIÊN BẢN QUYẾT ĐỊNH KIẾN TRÚC

## 6. Vì sao đưa ADR vào phụ lục

Tám biên bản quyết định kiến trúc được lập trong giai đoạn thiết kế (07/2026),
**trước** khi hệ thống được xây xong. Giá trị của chúng ở đây có hai mặt:

* Chúng chứng minh có **quy trình thiết kế** — mỗi quyết định có bối cảnh, các
  phương án, và lý do chọn.
* Quan trọng hơn: **ba trong tám biên bản đã bị thay thế bởi hiện thực**, và
  chính sự thay thế đó là dữ liệu về quá trình thiết kế. Giấu đi thì mất một phần
  câu chuyện; nêu ra thì có được một lập luận về việc thiết kế tiến hoá theo bằng
  chứng.

Ký hiệu trạng thái: ✅ **còn hiệu lực** · ⟲ **đã bị thay thế** · ⏸ **hoãn có chủ đích**

## 7. Bảng tám biên bản

| # | Quyết định | Trạng thái | Hiện thực cuối |
|---|---|---|---|
| ADR-001 | Không tạo bảng tổ chức riêng — không gian làm việc **chính là** đơn vị tổ chức | ⟲ **Đã thay thế** | Tách ba tầng: Tổ chức ⊃ Không gian làm việc ⊃ Dự án. Xem §8 |
| ADR-002 | Vai trên tài khoản chỉ là vai cấp hệ thống; quyền theo tư cách thành viên + thư viện phân quyền | ⟲ **Thay thế một phần** | Mô hình gán vai theo phạm vi; thư viện phân quyền chạy **chế độ bóng**, chưa cưỡng chế |
| ADR-003 | Tách bộ dữ liệu logic khỏi ảnh chụp bất biến của nó | ✅ Còn hiệu lực | Bảng phiên bản danh mục, ghim được — xem Phụ lục A §4.4 |
| ADR-004 | Tách bốn bảng cho vòng đời mô hình | ⏸ Hoãn | Hiện quản lý mô hình như hiện vật của tác vụ huấn luyện |
| ADR-005 | Tách **hạn mức** khỏi **thực dùng** | ✅ Còn hiệu lực | Hai nguồn số liệu khác nhau, có chủ đích — Chương 1 §2.5 |
| ADR-006 | Giữ ba bảng nhật ký, hoãn mô hình bảy tầng | ⏸ Hoãn có chủ đích | Nhật ký kiểm toán + nhật ký có cấu trúc; mô hình bảy tầng chưa cần ở quy mô này |
| ADR-007 | Giữ hai bảng pháp lý, hoãn quy trình duyệt sáu bảng | ⏸ Hoãn, đã mở rộng | Hiện có sáu bảng nhóm pháp lý gồm bản thảo và lịch sử sự kiện — vượt phạm vi ADR gốc |
| ADR-008 | Cách ly tổ chức bằng **tầng trung gian + bộ lọc ở tầng truy cập dữ liệu**; **hoãn** chính sách bảo mật mức hàng | ⟲ **Đã thay thế — quan trọng nhất** | Chính sách mức hàng trở thành **tầng cưỡng chế chính**. Xem §9 |

## 8. ADR-001 bị thay thế như thế nào, và vì sao

**Quyết định gốc:** không gian làm việc chính là đơn vị tổ chức; không cần bảng
riêng cho tổ chức.

**Vấn đề lộ ra khi xây:** gộp hai khái niệm này buộc **mọi ranh giới tổ chức công
việc phải trở thành một ranh giới cách ly**. Nghĩa là mỗi nhóm công việc mới lại
là một đơn vị thuê bao mới — không dùng được cho một trường có nhiều lớp cùng thu
dữ liệu.

**Thiết kế cuối** tách ba tầng, mỗi tầng một trách nhiệm:

| Tầng | Trách nhiệm |
|---|---|
| **Tổ chức** | Ranh giới **cách ly và quản trị** cao nhất. Là thứ chính sách bảo mật bảo vệ, là thứ hoá đơn tính theo, là thứ không được rò sang nhau |
| **Không gian làm việc** | Không gian **tổ chức công việc** bên trong một tổ chức |
| **Dự án** | Phạm vi hoạt động hẹp hơn nữa |

Đây là **tinh chỉnh thiết kế**, không phải bỏ cam kết: mục tiêu đa tổ chức được
giữ nguyên, chỉ được đặt vào đúng tầng.

**Giới hạn phải nêu kèm:** hai tầng dưới **có bảng nhưng không có điểm cuối API
nào**. Chúng là cấu trúc dữ liệu, chưa phải bề mặt vận hành — xem Chương 3 §3.1
và Kết luận §2.1.

## 9. ADR-008 bị thay thế như thế nào — biên bản quan trọng nhất

**Quyết định gốc (07/2026):** cách ly tổ chức bằng tầng trung gian phân giải tổ
chức, cộng bộ lọc ở tầng truy cập dữ liệu. Chính sách bảo mật mức hàng được
**hoãn** sang giai đoạn sau vì chi phí triển khai.

**Bằng chứng làm đảo quyết định:** trong chính hệ thống này, **ba hàm ở tầng truy
cập dữ liệu không lọc theo tổ chức** — xoá một mẫu, xoá mẫu theo lớp, cập nhật
đường dẫn lưu trữ. Ba hàm ấy tồn tại **sau khi** ADR-008 được áp dụng, do người
viết chúng không nhớ quy ước.

Đây chính là lập luận mạnh nhất cho việc chuyển cơ chế cưỡng chế xuống tầng cơ sở
dữ liệu, và nó là **bằng chứng thật chứ không phải giả định**:

> Vá tay được ba hàm đã biết. Chính sách ở tầng cơ sở dữ liệu vá luôn những hàm
> **sẽ viết sau** mà tác giả quên lọc.

**Thiết kế cuối** giữ tầng trung gian (nó vẫn cần, để phân giải tổ chức từ phiên)
nhưng **không còn coi nó là ranh giới bảo mật**. Ranh giới nằm ở bốn tầng mô tả ở
Chương 3 §2.3.2, trong đó tầng thứ tư — tách vai cơ sở dữ liệu — là tầng biến cơ
chế từ *lời khuyên* thành *bảo đảm*.

**Bài học tổng quát, đáng giữ trong quyển:** một cơ chế bảo mật dựa vào việc lập
trình viên nhớ làm đúng sẽ hỏng ở **hàm được viết sau khi quy ước được đặt ra** —
và hỏng theo kiểu không sinh triệu chứng.

## 10. ADR-002 và chế độ bóng

**Quyết định gốc:** dùng một thư viện phân quyền có hỗ trợ miền, với bốn cấp phạm
vi và mười ba vai.

**Hiện trạng đo được từ nhật ký khởi động của chính ứng dụng:**

```
nạp chính sách: 329 quy tắc, 14 gán vai (hệ thống=4, tổ chức=10, không gian làm việc=0, dự án=0)
chế độ phân quyền: bóng
```

Đọc thẳng: hai phạm vi dưới có **0 gán vai** — được khai báo trong mô hình nhưng
chưa có ai được cấp quyền ở đó, khớp với §8. Và **chế độ bóng** nghĩa là thư viện
**tính toán quyết định nhưng không cưỡng chế**; quyết định thực tế vẫn do đường
phân quyền trực tiếp đưa ra.

**Phát biểu chính thức, phải giữ nhất quán:**

> Mô hình dữ liệu và kiến trúc phân quyền hỗ trợ một hệ phân cấp mở rộng được,
> nhưng cưỡng chế lúc chạy hiện chỉ **chứng minh được** ở phạm vi hệ thống và
> phạm vi tổ chức. Hai phạm vi dưới chưa có bề mặt API nghiệp vụ và chưa có gán
> vai thực tế.

**Không** được phát biểu "hệ thống cưỡng chế phân quyền ở bốn phạm vi". Và **không
xây thêm hai tầng phạm vi chỉ để khớp thiết kế ban đầu** — ghi nhận sai lệch
trung thực tốt hơn nhiều so với dựng vội hai tầng chưa có nghiệp vụ thật đứng sau.

## 11. Bốn sai lệch khác so với thiết kế ban đầu

Ngoài ba ADR bị thay thế, còn bốn sai lệch giữa đề cương và hiện thực. Cả bốn đều
là **tinh chỉnh có lý do**, không phải cam kết bị bỏ:

| # | Đề cương nói | Hiện thực | Cách xử lý trong quyển |
|---|---|---|---|
| 1 | Kho đối tượng chuyên dụng | Hệ tệp cục bộ + kho lưu trữ ngoài | Ràng buộc ngân sách (RB-T2). Giữ kho đối tượng ở phần Hướng phát triển |
| 2 | Thư viện trích đặc trưng **toàn thân** | Chỉ dùng phần **bàn tay** | Gói toàn thân có trong khai báo phụ thuộc nhưng **không dòng mã nào dùng**. Con số 126 chiều/khung vốn đã là con số của phần bàn tay, nên phần định lượng không đổi |
| 3 | Máy chủ định danh tập trung | Xác thực tự triển khai | Bỏ khỏi phần công nghệ; giữ ở Hướng phát triển |
| 4 | Lược đồ hình sao cho phân tích | Lược đồ quan hệ chuẩn hoá | Sửa mô tả cho khớp hiện thực |

**Câu nên dùng trong quyển cho sai lệch số 2:**

> Thiết kế được tinh chỉnh sang biểu diễn chỉ dùng thông tin bàn tay, vì đường xử
> lý cuối chỉ sử dụng thông tin đó; thu nhận tư thế toàn thân và biểu cảm khuôn
> mặt vẫn nằm ngoài phạm vi triển khai.

## 12. Ba việc kiểm tra trước khi in

| # | Việc | Trạng thái | Vì sao |
|---|---|---|---|
| 1 | **Sửa kịch bản đo để ghi phiên bản mã vào artefact** | **xong 17/08/2026** | Cờ `cong_bo_duoc` nay có hai vế: hết ca mờ **và** xác định được phiên bản mã trên cây sạch |
| 2 | **Đóng phép đo cách ly trên mã bản cuối** (Chương 4 §5.2bis) | **xong 17/08/2026** | Đo lại trên ảnh chụp `4e961192`: 0/450, 0/180, 0 ca mờ, hậu điều kiện đạt |
| 3 | Chụp lại số hàng của các bảng dữ liệu (Phụ lục A §4) | **chưa** | Ảnh chụp hiện tại là ngày 10/08/2026; ba bảng đã thay đổi đáng kể |
| 4 | Chạy lại toàn bộ bộ kiểm thử và chép **số thật** kèm số bỏ qua | **xong 17/08/2026** | 2.528 xanh / 0 đỏ / 1 bỏ qua — số đếm tĩnh **không phải** số đã chạy xanh |
| 5 | Đếm lại quy mô mã nguồn và lược đồ | **xong 17/08/2026** | Số cũ lệch tới 15 % ở phần mã kiểm thử |
| 6 | Rà ba phát biểu đã hạ mức trên **cả bốn** vị trí: Tóm tắt, Chương 3, Chương 4, Kết luận | **chưa** | Lệch một chỗ là một câu hỏi phản biện không trả lời được |

**Việc 1 phải xong trước việc 2, và đã làm đúng thứ tự đó:** sửa kịch bản đo
trước, rồi mới đo lại. Làm ngược thì lượt đo mới lại sinh ra một artefact không tự
khai được phiên bản, và toàn bộ vấn đề lặp lại nguyên vẹn.
