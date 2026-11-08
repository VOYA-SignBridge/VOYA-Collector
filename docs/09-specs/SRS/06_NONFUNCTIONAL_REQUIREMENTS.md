# 6. Yêu cầu phi chức năng (Nonfunctional Requirements)

*Mỗi yêu cầu có một mã, một phát biểu **kiểm chứng được**, và một cách kiểm. Yêu
cầu không nêu được cách kiểm là yêu cầu không dùng được — nó không phân biệt nổi
hệ thống đạt với hệ thống không đạt.*

**Quy ước đọc bảng kết quả:** cột *Kết quả đo* chỉ được điền khi phép đo đó có
**đối chứng dương** (chứng minh dụng cụ chạm đúng đối tượng). Phép đo thiếu đối
chứng dương ghi `chưa kết luận`, không ghi số.

---

## 6.1 Hiệu năng (Performance)

### 6.1.1 Yêu cầu

| Mã | Yêu cầu | Cách kiểm |
|---|---|---|
| NFR-P1 | Độ trễ các điểm cuối đọc thường dùng **dưới 100 ms tại phân vị 95** trong điều kiện không tranh chấp | Đo độ trễ cơ sở: 1.000 lượt/điểm cuối, ba lượt chạy độc lập, lấy trung vị của ba giá trị phân vị |
| NFR-P2 | Trích điểm mốc tại trình duyệt đạt tối thiểu **15 khung/giây** trên máy tính xách tay phổ thông, để cửa sổ 60 khung hoàn tất trong ≈ 4 giây | Đo trên máy tham chiếu nêu ở Phụ lục B |
| NFR-P3 | Thao tác thu mẫu **không được chặn** giao diện: mọi bước xử lý nặng chạy trên tiến trình nền | Kiểm chức năng: sau khi bấm Lưu, giao diện trả về trong dưới 1 giây kèm mã tác vụ |
| NFR-P4 | Một mẫu sau chuẩn hoá chiếm **không quá 100 KiB** ở phân vị 95 | Thống kê trên toàn bộ tệp đặc trưng |
| NFR-P5 | Biểu diễn điểm mốc giảm **trên 90 %** dung lượng so với video nguồn | Đo ghép cặp khớp thời lượng, báo cáo kèm cỡ mẫu và khoảng phân bố |

### 6.1.2 Kết quả đo độ trễ (NFR-P1)

**Giao thức** — đo ngày 15/08/2026:

```
khởi động    50 lượt / điểm cuối / lượt chạy, KHÔNG tính vào thống kê
đo           1.000 lượt / điểm cuối / lượt chạy
đồng thời    1
lặp lại      3 lượt chạy độc lập
gộp          trung vị của BA giá trị p50/p95/p99, KHÔNG gộp 3.000 mẫu
```

Ba lượt được giữ riêng trong artifact. Gộp 3.000 mẫu lại sẽ **giấu một lượt bất
thường**: nếu lượt hai chậm gấp đôi vì máy bận việc khác, tổng mẫu vẫn cho một
con số trông hợp lý và không ai biết.

**Kết quả** (đơn vị mili giây, trung vị của 3 lượt):

| Lớp đường đi | Điểm cuối | p50 | p95 | p99 | Thân | Quy mô |
|---|---|---:|---:|---:|---:|---|
| công khai | `/health` | 4,4 | 6,4 | 8,1 | 79 B | — |
| công khai | `/api/v1/billing/plans` | 6,8 | 8,8 | 10,7 | 2.419 B | 4 mục |
| xác thực/đọc | `/api/v1/auth/me` | 20,8 | 24,3 | 27,7 | 202 B | — |
| xác thực/đọc | `/api/v1/billing/me` | 28,3 | 33,1 | 39,4 | 1.729 B | — |
| theo tenant | `/api/v1/vocabulary/registry` | 16,3 | 18,9 | 25,9 | 4.499 B | — |
| theo tenant | `/api/v1/training/dataset-info` | 21,3 | 25,0 | 29,4 | 132 B | — |
| theo tenant | `/api/v1/classes/list` | 5,2 | 6,4 | 7,7 | 22 B | **0 mục** |

`measurement_status = OK` · vân tay container khớp trước/sau · 21.000/21.000 lượt
phục vụ · 0 lỗi ứng dụng · 0 lỗi truyền · 0 lượt bị giới hạn tần suất.

**Kết luận: NFR-P1 đạt** — p95 cao nhất là 33,1 ms, dưới ngưỡng 100 ms.

**Ba giới hạn phải đọc kèm bảng, không được bỏ:**

1. **Đây là độ trễ cơ sở, không phải phép thử tải.** Đồng thời = 1. Bảng trả lời
   *"một yêu cầu tốn bao lâu khi không có ai tranh chấp"*, **không** trả lời *"hệ
   thống chịu được bao nhiêu yêu cầu mỗi giây"*.
2. **`/classes/list` trả về 0 mục.** Con số 5,2 ms đại diện cho *đường xử lý
   tenant-scoped với tập kết quả rỗng*. Nó **không** phải hiệu năng truy vấn một
   danh mục có dữ liệu, và không được dùng để suy ra bất cứ điều gì về khả năng
   mở rộng theo số lớp.
3. **Giới hạn tần suất đã được nâng trần ở môi trường đo.** Đây là thuộc tính của
   môi trường đo, không phải "tắt một cơ chế sản xuất rồi coi như nó không tồn
   tại" — trần thật vẫn chạy trên sản xuất và đã đo được nó chặn 868/1.200 lượt.

**Hai cái bẫy dụng cụ đã trả giá để biết**, ghi lại vì chúng cho ra bảng số liệu
trông hoàn toàn bình thường:

* **`127.0.0.1` chứ không phải `localhost`.** Cổng chỉ mở trên IPv4; `localhost`
  phân giải ra `::1` trước và mỗi lượt phải chờ hết hạn rồi mới lùi lại. Một lượt
  đo mắc lỗi này cho p50 của `/health` là **2.063 ms — gấp 29 lần** con số thật.
* **Container đo phải tách khỏi container thí nghiệm cách ly.** Hai sự cố xảy ra
  trong cùng một buổi: một container bị dựng lại **giữa** lượt benchmark (213
  lượt hỏng đi thẳng vào bảng), và một cây fixture được mount làm `/classes/list`
  nhảy từ 22 byte lên 2.154 byte — **cùng URL, cùng bảng, khối lượng công việc
  khác hẳn**. Trường hợp thứ hai nguy hiểm hơn: container sập thì thấy ngay,
  workload bị đổi thì cho ra con số hoàn toàn đẹp.

### 6.1.3 Kết quả đo hiệu quả lưu trữ (NFR-P4, NFR-P5)

**Phía điểm mốc** — đo 15/08/2026, n = 3.871 tệp `.npz`:

```
tổng     = 146,0 MiB
trung bình = 38,6 KiB      trung vị = 42,6 KiB
p5       = 14,1 KiB        p95      = 82,8 KiB
```

**NFR-P4 đạt:** p95 = 82,8 KiB, dưới ngưỡng 100 KiB.

Phân bố rộng hơn nhiều so với một con số đơn lẻ gợi ý — p5 tới p95 gấp gần **sáu
lần**. Nguyên nhân: `.npz` là định dạng nén, và một chuỗi mà một tay vắng mặt
phần lớn thời gian gồm nhiều số 0 liên tiếp nên nén rất tốt.

**Phép đo ghép cặp video ↔ điểm mốc** — chạy 16/08/2026 trên 200 clip QIPEDC,
khớp thời lượng, n = 54:

> **Kết quả công bố: giảm 92,2 %.** Cam kết "trên 90 %" **được xác nhận trên tổng
> dung lượng và trên trung vị, nhưng KHÔNG đúng cho mọi mẫu.**

**Vì sao phải đo trên nguồn ngoài:** đây là hệ quả trực tiếp của ràng buộc RB-D5.
Kho dữ liệu của hệ thống có **8.784 tệp `.npz` và 0 video** — đường thu qua webcam
không sinh video, nên không có gì để đo ngược lại. Một ràng buộc thiết kế tự chặn
mất một phép đo, và điều đó phải nói ra chứ không được lấp bằng một con số vay
mượn.

### 6.1.4 Sức chứa và thông lượng — **chưa đo**

| Hạng mục | Trạng thái |
|---|---|
| Số người dùng đồng thời chịu được | ○ **Chưa đo.** Không có thí nghiệm tải |
| Số giao dịch mỗi giây | ○ **Chưa đo** |
| Cách ly hiệu năng giữa các tổ chức | ○ **Chưa chứng minh.** Hệ thống có hạn mức và giới hạn tần suất, nhưng hai thứ đó **không** chứng minh được một tổ chức không làm chậm tổ chức khác. Khẳng định đó cần thí nghiệm tạo tải ở tổ chức A rồi quan sát độ trễ của tổ chức B |

Ba dòng trên để trống **có chủ ý**. Một bản SRS điền vào đó những con số ước
lượng sẽ tạo ra cam kết mà không ai kiểm chứng được.

---

## 6.2 Độ tin cậy (Reliability)

| Mã | Yêu cầu | Cách kiểm | Trạng thái |
|---|---|---|:--:|
| NFR-R1 | Mất kết nối trong lúc thu **không được làm mất bản thu**: dữ liệu đã thu giữ lại ở trình duyệt và thử lại được | Kiểm thử ngắt mạng ở bước gửi | ✓ |
| NFR-R2 | Bản gốc tải lên phải được **lưu trước** mọi bước chuẩn hoá | Kiểm thứ tự ghi trong luồng xử lý | ✓ |
| NFR-R3 | Xoá là **xoá mềm**, khôi phục được cho tới khi dọn hẳn | Kiểm thử khôi phục từ thùng rác ở cả ba mức xoá | ✓ |
| NFR-R4 | Sao lưu cơ sở dữ liệu chạy **theo lịch**, và phải **diễn tập khôi phục được** | Chạy chế độ `--drill`; kiểm toàn vẹn bằng phương pháp phát hiện được tệp cụt | ✓ |
| NFR-R5 | Nguồn sự thật và bản sao truy vấn phải có **cơ chế đối soát định kỳ** | Kiểm sự tồn tại và kết quả của tác vụ đối soát | ✓ |
| NFR-R6 | Hệ thống phải phát hiện được **mã đang chạy không khớp mã nguồn** | Công cụ kiểm độ tươi triển khai, bắt được ba kiểu lệch | ✓ |
| NFR-R7 | Tác vụ nền thất bại phải **thông báo tới chủ sở hữu tác vụ**, không chỉ ghi log | Kiểm thử tác vụ huấn luyện hỏng | ✓ |

**Giới hạn phải nêu:** cơ chế **thử lại** và **tính lũy đẳng** hiện **chưa đồng
đều** giữa các đường xử lý nền. Việc tạo tài nguyên và tải đối tượng lên kho ngoài
chưa bảo đảm chạy lại nhiều lần cho cùng kết quả. Đây là hạn chế **đã biết**,
không phải điều chưa rà soát. Kết luận đúng mức cho nhóm chức năng tương ứng là
*"đạt về năng lực, có hạn chế về độ tin cậy"* — không phải *"đạt một phần"* về
năng lực.

**Ba chi tiết bắt buộc của cơ chế sao lưu**, mỗi cái từ một lần sai:

* **Thứ tự thao tác: kết xuất trước, nén sau.** Đảo thứ tự sinh ra tệp trông hợp
  lệ nhưng thiếu phần đuôi.
* **Kiểm toàn vẹn phải đọc hết nội dung.** Lệnh liệt kê nội dung tệp sao lưu
  **không** phát hiện được tệp bị cụt — nó chỉ đọc phần mục lục.
* **Nhiều bản, nhiều nơi.** Cơ chế mã hoá và sao chép sang ổ khác **đã có, mặc
  định tắt**. Phải bật khi triển khai thật.

**Nguyên tắc nền:** *một bản sao lưu chưa được diễn tập khôi phục là một bản sao
lưu chưa tồn tại.*

**Về khả năng sẵn sàng (availability):** hệ thống chạy trên **một máy chủ duy
nhất**, không có dự phòng, không có cơ chế chuyển đổi dự phòng. Vì vậy bản SRS
này **không cam kết một con số uptime nào**. Cam kết 99,9 % trên hạ tầng một máy
là một con số không có cơ sở. Điều cam kết được là ba thứ cụ thể trong bảng trên:
không mất dữ liệu khi mất mạng, khôi phục được từ bản sao lưu, và phát hiện được
khi mã đang chạy lệch mã nguồn.

**Thiết kế fail-closed có trả giá bằng khả năng sẵn sàng, và đó là lựa chọn có ý
thức:** `sot-init` không xác minh được danh mục thì **chặn toàn bộ hệ thống khởi
động**. Một máy không xác thực được danh mục thì không được phép phục vụ.

---

## 6.3 An toàn thông tin và bảo mật (Safety and Security)

### 6.3.1 Cách ly dữ liệu giữa các tổ chức

| Mã | Yêu cầu | Cách kiểm | Trạng thái |
|---|---|---|:--:|
| NFR-S1 | **Cách ly cưỡng chế ở tầng cơ sở dữ liệu.** Một truy vấn không khai báo tổ chức trả về **0 hàng** | Đo đối kháng qua API: nhóm đúng quyền – sai tổ chức phải bị chặn 100 %, **kèm đối chứng dương** chứng minh chủ sở hữu làm được | ✓ cơ chế · △ phép đo |
| NFR-S2 | Ứng dụng **không được tự vô hiệu hoá** cơ chế cách ly | Vai chạy không có quyền DDL, không có quyền vượt chính sách | ✓ |
| NFR-S3 | Ngữ cảnh tổ chức **giới hạn trong phạm vi giao dịch**, không rò sang yêu cầu kế tiếp trên cùng kết nối | Kiểm thử tuần tự hai yêu cầu của hai tổ chức trên cùng kết nối | ✓ |
| NFR-S4 | Công việc nền xuyên tổ chức đi qua **một phạm vi riêng biệt**, không mượn định danh của tổ chức nào | Kiểm rằng phạm vi hệ thống là biến ngữ cảnh riêng, không phải giá trị đặc biệt của biến tổ chức | ✓ |
| NFR-S5 | Mọi thao tác nhạy cảm để lại **nhật ký kiểm toán bền vững**, và việc ghi nhật ký **từ chối khi thiếu ngữ cảnh** | Kiểm sự tồn tại bản ghi; kiểm hành vi từ chối khi không có phạm vi | ✓ |
| NFR-S6 | Tạo tác danh mục phải **có bằng chứng giả mạo**: sửa được nhưng không giấu được | Ma trận chín kịch bản giả mạo | ✓ 8/9, 1 giới hạn |
| NFR-S7 | Không xác minh được nguồn sự thật thì hệ thống **dừng**, không suy đoán | Kiểm mã thoát của tiến trình khởi tạo và trạng thái các dịch vụ phụ thuộc | ✓ |

**Độ phủ cơ chế cách ly** (truy vấn CSDL đang chạy, 17/08/2026):

| Chỉ số | Giá trị |
|---|---|
| Bảng mang cột định danh tổ chức | 34 |
| Bảng bật chính sách bảo mật mức hàng | 32 |
| Bảng bật cờ cưỡng chế với chủ sở hữu bảng | **32 / 32 = 100 %** |
| **Độ phủ** | **32 / 34 ≈ 94,1 %** |

Hai bảng còn lại được nêu **đích danh** thay vì để thành một con số trừ đi:
`tenants` (truy vấn phân giải ngữ cảnh phải đọc nó **trước khi** ngữ cảnh tồn
tại) và `tenant_purges` (chỉ ghi/đọc qua đường quản trị nền tảng). Trường hợp
`tenants` đáng chú ý về mặt lập luận: nó cho thấy **cơ chế cách ly không thể tự
bảo vệ chính cái bảng định nghĩa ra các đơn vị cách ly** — một giới hạn có tính
cấu trúc, không phải sơ suất bỏ quên.

**Về trạng thái phép đo cách ly đối kháng — phải nói thẳng:**

> Lượt đo ngày 15/08/2026 **đã bị loại khỏi phân tích**. Không phải vì kết quả
> xấu, mà vì phép đo **không chứng minh được dụng cụ đang chạm đúng đối tượng**:
> đối chứng dương với các tài nguyên đọc từ **hệ tệp** không đạt — tài khoản thử
> nghiệm không đọc được lớp và mẫu **của chính nó** (404). Khi đó mọi kết quả "đã
> chặn" không phân định được giữa *cách ly hoạt động đúng* và *tài khoản vốn
> không đọc được gì*.
>
> **Phần còn giá trị:** trong 630 lần thử đối kháng, 390 ca trả `403` và 120 ca
> trả `401` đi qua đường PostgreSQL và tầng xác thực thật — chúng vẫn là bằng
> chứng hợp lệ cho những đường đó. 120 ca `404` trên đường lớp/mẫu thì không, vì
> chúng trả 404 cho **cả chủ sở hữu**. Không được dùng 390 ca kia để cứu 120 ca
> này.
>
> **Vì vậy: không có số liệu định lượng về tỉ lệ vi phạm cách ly trong bản SRS
> này.** Cơ chế có, kiểm thử có; **phép đo** thì đang chờ bước gieo fixture nhất
> quán trên cả PostgreSQL lẫn kho tệp.

**Bốn tầng cưỡng chế cách ly** (mỗi tầng bịt một lối vòng mà ba tầng còn lại để hở):

1. Lọc theo tổ chức ở tầng ứng dụng
2. Gán phạm vi tự động ở tầng trung gian
3. Chính sách bảo mật mức hàng ở tầng cơ sở dữ liệu, cộng khoá ngoại ghép mang
   định danh tổ chức (22/117 khoá ngoại)
4. **Tách vai cơ sở dữ liệu** — vai chạy của ứng dụng không phải siêu người dùng,
   không có `BYPASSRLS`, không có quyền DDL

Tầng thứ tư là tầng biến cơ chế từ *lời khuyên* thành *bảo đảm*: cơ sở dữ liệu
miễn trừ chính sách **vô điều kiện** cho vai siêu người dùng, nên cờ cưỡng chế
với chủ sở hữu bảng vẫn chưa đủ.

**Một cái bẫy đã mắc BA LẦN trong hai ngày**, đáng ghi vì nó là kiểu hỏng ngược
đời: khi một truy vấn chạy **trước khi** biết tổ chức, chính sách khớp 0 hàng, và
mã ứng dụng đọc "0 hàng" thành **"không có gì"** thay vì **"chưa có ngữ cảnh"**.
Cách ly fail-closed ở tầng CSDL vẫn có thể bị **tầng ứng dụng diễn giải sai thành
fail-open**.

### 6.3.2 Kết quả đo toàn vẹn nguồn sự thật (NFR-S6)

Ma trận chín kịch bản giả mạo, đo 16/08/2026, chạy qua **đúng đường consumer của
ứng dụng**, mỗi lần đổi đúng một biến:

| Ca | Thuộc tính kiểm tra | Kết quả | Đánh giá |
|---|---|---|---|
| S1 | artifact + bản kê + chữ ký đều hợp lệ | ACCEPT | Đạt |
| S2 | đổi **đúng một byte** trong artifact sau khi ký | REJECT | Đạt |
| S3 | sửa mã băm trong bản kê, giữ chữ ký cũ | REJECT | Đạt |
| S4 | chữ ký hợp lệ về mật mã, **người ký KHÔNG tin cậy** | REJECT | Đạt |
| S5 | chữ ký hỏng | REJECT | Đạt |
| S6 | thiếu chữ ký khi chính sách đòi ký | REJECT | Đạt |
| S7 | **hồi quy phiên bản** | ACCEPT; không xoá tài nguyên mới, nhưng giá trị dùng chung bị lùi | **GIỚI HẠN** |
| S8 | phiên bản mới, nguồn tin cậy | ACCEPT | Đạt |
| S9 | công bố chỉ bổ sung, giữ hàng có sẵn | ACCEPT | Đạt |

**Không đọc kết quả này là "9/9 đạt".** Phép đo hợp lệ ở cả chín ca; **thuộc tính
bảo mật đạt ở tám**. Ca thứ chín tìm ra một giới hạn có thật, và đó là phần đáng
giá nhất của lượt đo.

### 6.3.3 Bảo mật danh tính và truy cập

| Mã | Yêu cầu | Cách kiểm | Trạng thái |
|---|---|---|:--:|
| NFR-C1 | Cổng truy cập **mặc định từ chối**: điểm cuối mới không khai báo công khai thì tự động yêu cầu xác thực | Kiểm ở tầng trung gian, **không** ở từng điểm cuối; liệt kê toàn bộ điểm cuối và đối chiếu danh sách ngoại lệ | ✓ |
| NFR-C2 | Mật khẩu lưu dạng **băm có muối**; không có đường đọc ngược | Rà soát lược đồ và rà soát mô hình trả về của API | ✓ |
| NFR-C3 | Phiên đăng nhập có **ba mức thu hồi** | Kiểm thử từng mức | ✓ |
| NFR-C4 | **Xác thực hai yếu tố** theo chuẩn TOTP, kèm mã khôi phục dùng một lần | Kiểm bằng **vector thử của tiêu chuẩn**, không chỉ kiểm "đăng nhập được" | ✓ |
| NFR-C5 | Thao tác **không hoàn tác được** đòi xác thực lại trong phiên | Kiểm thử cho ba use case: dọn sạch dữ liệu tổ chức, công bố văn bản pháp lý, đổi gói cước | ✓ |
| NFR-C6 | Giới hạn tần suất tính theo **địa chỉ IP thật**, không cho phía gọi tự khai | Kiểm rằng tiêu đề do phía gọi đặt không ảnh hưởng bộ đếm | ✓ |
| NFR-C7 | Biểu mẫu đăng nhập **không được dùng để dò tên tài khoản**: sai tên và sai mật khẩu trả cùng thông báo và cùng độ trễ | Kiểm thử so sánh hai nhánh | ✓ |
| NFR-C8 | Liên kết đặt lại mật khẩu chỉ trỏ tới **danh sách máy chủ được phép** | Kiểm thử với tiêu đề máy chủ giả mạo | ✓ |

**Vì sao NFR-C4 phải kiểm bằng vector thử:** một cài đặt sai lệch múi giờ vẫn cho
đăng nhập được với ứng dụng sinh mã cùng lỗi, nhưng **không tương thích với ứng
dụng chuẩn**. Kiểm "đăng nhập được" không phát hiện ra điều đó.

**Chiến lược chống dò mật khẩu — tăng dần theo bậc:** trong mười lần thất bại
đầu, người dùng thử lại được ngay; từ lần kế tiếp, hệ thống áp thời gian chờ tăng
dần — nửa phút, hai phút, năm phút, rồi mười lăm phút — và giữ ở bậc cuối cho tới
hết cửa sổ một giờ. Người dùng thật gõ nhầm vài lần gần như không bị ảnh hưởng;
một kịch bản dò tự động mất hàng giờ cho vài chục lần thử.

**Một bài học về lọc dữ liệu trả về:** bỏ khai báo `response_model` của một điểm
cuối tương đương với **gỡ bộ lọc bảo mật** — và đã làm **rò mã băm mật khẩu** ra
ngoài trong một lần sửa. Mô hình trả về ở đây không phải chuyện tài liệu hoá; nó
là một cơ chế bảo vệ.

### 6.3.4 Bảo vệ dữ liệu chủ thể

| Yêu cầu | Trạng thái | Ghi chú |
|---|---|---|
| Đồng thuận gắn với **người ký**, có phiên bản | ✓ | Thang ba mức |
| Đồng thuận **chi phối đường phát hành dữ liệu** | ✓ | Bốn đường dữ liệu đều qua cổng đồng thuận |
| Văn bản pháp lý bất biến sau khi công bố | ✓ | Trigger ở tầng CSDL, không phải kiểm tra ở ứng dụng |
| Truy được dữ liệu về chủ thể | △ | **Chỉ 43,4 %** số mẫu quy được về người ký (đo 10/08/2026) |
| Xoá khỏi lưu trữ khi thu hồi | ○ | Là thao tác vận hành, **làm tay** |
| Thu hồi giấy phép đã cấp cho bên thứ ba | ○ | Cần cơ chế pháp lý, không phải cơ chế phần mềm |

**Bốn nghĩa của "thu hồi", và hệ thống chỉ thi hành nghĩa thứ hai:**

| # | Nghĩa | Đã thi hành? |
|---|---|---|
| 1 | Thu hồi quyền truy cập của một người | Có — qua cơ chế cách ly và vai |
| 2 | Gỡ khỏi các bản phát hành **mới** | **Có** |
| 3 | Xoá khỏi lưu trữ | Không |
| 4 | Thu hồi giấy phép **đã cấp** cho bên thứ ba | Không |

Hứa "xoá là biến mất hoàn toàn" là hứa nghĩa 3 và 4 trong khi chỉ làm nghĩa 2.
Giao diện nói thẳng điều này, và **có kiểm thử ghim đúng câu chữ đó**.

**Con số 43,4 % là kết quả cần báo cáo, không phải khiếm khuyết cần giấu.** Định
danh tài khoản thu phủ 95,7 % số mẫu, còn định danh người ký chỉ phủ 43,4 % —
nghĩa là **56,6 % kho dữ liệu không truy được về người có bàn tay trong đó**.
Nguyên nhân là khoảng cách giữa mô hình đúng và dữ liệu lịch sử: mắt xích *mẫu –
người ký* chỉ thiết lập được đáng tin **tại thời điểm thu**, và với phần dữ liệu
cũ, chuỗi nguồn gốc đứt ở đúng vị trí không dựng lại được.

---

## 6.4 Khả năng thích nghi và chuyển đổi (Adaptability and Portability)

### 6.4.1 Tính duy trì được

| Mã | Yêu cầu | Cách kiểm | Trạng thái |
|---|---|---|:--:|
| NFR-M1 | Toàn bộ hệ thống **dựng lại được từ mã nguồn** bằng một lệnh trên máy sạch | Diễn tập triển khai trên máy thứ hai | ✓ **đã thực hiện** |
| NFR-M2 | Cấu hình tách khỏi mã theo Twelve-Factor; đổi cấu hình **không cần dựng lại ảnh** | Rà soát; kiểm thử đổi biến môi trường | ✓ |
| NFR-M3 | Thay đổi cấu trúc dữ liệu chia **hai loại**: bước tự động lúc khởi động chỉ được **thêm**; mọi thay đổi một chiều qua lệnh di trú tường minh | Rà soát chính sách DDL; kiểm nợ lược đồ bằng ba lần khởi động liên tiếp | ✓ |
| NFR-M4 | Backend **từ chối khởi động** khi phiên bản lược đồ lệch, theo **cả hai chiều** | Kiểm thử với lược đồ cũ hơn và mới hơn | ✓ |
| NFR-M5 | Lệnh di trú có **chốt chặn đích đến** | Kiểm thử với biến đích không khớp | ✓ |
| NFR-M6 | Bộ kiểm thử chạy trong môi trường **giống môi trường thật**, trên mạng của các dịch vụ | Hạ tầng kiểm thử đóng gói riêng | ✓ |
| NFR-M7 | Giao diện hỗ trợ **đa ngôn ngữ**, không có chuỗi cứng trong mã | Công cụ đo độ phủ i18n chạy trong cổng trước triển khai | ✓ công cụ · △ độ phủ |
| NFR-M8 | Hệ thống phát ra **chỉ số và nhật ký có cấu trúc**, đủ để dựng cảnh báo | Kiểm sự tồn tại của chỉ số và của cảnh báo tương ứng | ✓ |

### 6.4.2 Bằng chứng cho NFR-M1 — triển khai máy thứ hai

Hệ thống đã được triển khai thành công lên một máy thứ hai với cấu hình phần cứng
khác. Ba điều được kiểm chứng, và **hai trong ba là phát hiện lỗi**:

1. **Quy trình không phụ thuộc máy cụ thể.** Kịch bản triển khai tự dò GPU và tự
   chọn lớp cấu hình phù hợp.
2. **Bước dựng lược đồ trên máy sạch từng thiếu sót nghiêm trọng.** Lần chạy đầu
   trên cơ sở dữ liệu dựng từ số không cho **22 kiểm thử đỏ**, do lược đồ tạo ra
   thiếu **2 bảng, 7 khoá ngoại và 14 cột** so với máy đang chạy. Không có lần
   triển khai này thì mọi máy mới sẽ nhận một lược đồ yếu hơn, **trong im lặng**.
3. **Một lớp lỗi chỉ xuất hiện trên máy Windows:** tệp kịch bản khởi động bị đổi
   ký tự xuống dòng theo quy ước Windows, khiến container giao diện chết trong
   vòng lặp với thông báo "không tìm thấy tệp thực thi". Đã cố định quy ước xuống
   dòng cho các tệp `.sh` bằng `.gitattributes`.

### 6.4.3 Khả năng chuyển môi trường

| Chiều | Trạng thái |
|---|---|
| Linux ↔ Windows (WSL2) | ✓ — cả hai đã chạy thật; lớp lỗi CRLF đã xử lý |
| Có GPU ↔ không GPU | ✓ — kịch bản tự dò; ép CPU bằng `--cpu` |
| Đường dẫn cơ sở `/` ↔ `/voya` | ✓ — cấu hình được, không sửa mã |
| GPU sm_86 ↔ sm_120 | ✓ — bản torch `cu128` phủ cả hai |
| Máy chủ đơn ↔ cụm nhiều máy | ○ **Chưa hỗ trợ.** RB-T1 |
| PostgreSQL ↔ hệ quản trị CSDL khác | ○ **Không** — cách ly dựa vào chính sách bảo mật mức hàng của PostgreSQL |

### 6.4.4 Khả năng mở rộng theo dữ liệu

| Hạng mục | Ảnh chụp 10/08/2026 | Ghi chú |
|---|---:|---|
| Mẫu | 3.860 | Bảng trung tâm `samples` |
| Lớp từ vựng | 63 | |
| Phiên thu | 250 | |
| Người ký | 4 | Chỉ 4 giá trị phân biệt — nguồn của con số 43,4 % |
| Tổ chức | 1 | Tổ chức `default`, nơi dữ liệu lịch sử nằm lại |
| Phiên bản danh mục | 89 | |
| Tác vụ huấn luyện | 90 | |

**Phải đọc kèm:** đây là quy mô của **một bản triển khai đang phát triển**, không
phải quy mô mục tiêu. Bản SRS này **không cam kết** một ngưỡng mở rộng nào, vì
không có thí nghiệm nạp dữ liệu ở nhiều quy mô để đo. Điều đã biết chắc là mô
hình dữ liệu không có rào cản cấu trúc nào ở các mức trên, và điều **chưa biết**
là điểm gãy nằm ở đâu.

### 6.4.5 Định dạng xuất dữ liệu

| Định dạng | Dùng cho |
|---|---|
| `.npz` (NumPy nén) | Tệp đặc trưng của một mẫu — 126 chiều × số khung |
| CSV | Nguồn sự thật của kho mẫu; bản xuất bộ dữ liệu |
| Google Sheets | Bản phản chiếu để đối soát bằng mắt; **giữ lại** dòng đã xoá mềm kèm dấu `deleted_at` |
| JSON | API, đặc tả OpenAPI, artifact của các phép đo |
| Ảnh chụp bộ dữ liệu có mã băm | Bản phát hành ghim phiên bản danh mục |
