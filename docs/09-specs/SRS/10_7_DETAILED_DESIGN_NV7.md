# 10.7 Thiết kế chi tiết — Nghiệp vụ 7: Vận hành hệ thống và nguồn sự thật

***6 use case** (UC701–UC706) cài đặt trên **13 điểm cuối** của hai bộ định tuyến
`sot_admin` và `health`, **cộng một bộ công cụ chạy trên dòng lệnh**.*

Nghiệp vụ này trả lời: **hệ thống có đang chạy đúng thứ ta nghĩ không?** Nó khác
Nghiệp vụ 6 ở chỗ **sai thì mất dữ liệu hoặc chạy sai mã**, chứ không phải sai
chính sách.

**Một đặc điểm phải nêu trước:** phần lớn use case của nghiệp vụ này **chạy ngoài
ứng dụng** — trên dòng lệnh của máy triển khai. Ranh giới thật của tác nhân A10 vì
thế là **quyền hệ điều hành**, không phải một vai trong hệ thống.

---

## CN7.1 — Quản lý nguồn sự thật và máy được cấp quyền (UC701, UC702)

### Mục đích

Bảo đảm mọi máy chủ chạy trên **cùng một danh mục đã được xác minh**, và một tạo
tác bị sửa thì **sửa được nhưng không giấu được**.

### Giao diện 1 — Quản lý SOT & thiết bị (`/admin/sot`, `SotAdminPage.tsx`, 433 dòng)

**Nhóm A — Đầu trang và xác minh**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| A1 | Tiêu đề | **"Quản lý SOT & thiết bị"** — *"Source of Truth: máy được cấp quyền, dữ liệu đã publish, schema."* |
| A2 | Nút | **"Làm mới"** |
| A3 | Nút | **"Verify SOT"** / "Đang verify…" |
| A4 | Kết quả xác minh | Thành công, hoặc **"Không xác minh được: {lỗi}"** |

**Nhóm B — Bốn thẻ trạng thái**

| No. | Thẻ | Nội dung |
|:--:|---|---|
| B1 | **"Version đã publish"** | Huy hiệu **`signed: {tên khoá}`** nếu người ký được tin cậy · **"chữ ký lạ"** nếu không · **"Chưa publish"** · **"Drive lỗi"** |
| B2 | **"Máy này"** | **"Máy ghi"** (có khoá riêng) hoặc **"Read-only (không có khóa)"** |
| B3 | **"Phiên bản lược đồ"** | Phiên bản lược đồ hiện hành |
| B4 | **"Máy được cấp quyền"** | Danh sách máy có khoá công khai được tin cậy |

**Nhóm C — Đăng ký và thu hồi máy**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| C1 | Ô nhập | Tên máy — thiếu thì báo **"Nhập tên máy"** |
| C2 | Ô dán khoá | Khoá công khai — thiếu thì báo **"Dán public key của máy"** |
| C3 | Nút đăng ký | Thành công: *"Đã đăng ký máy "{tên}""* |
| C4 | Nút thu hồi | Xác nhận: *"Thu hồi quyền SOT của máy "{tên}"?"*; thành công: *"Đã thu hồi "{tên}""* |

**Nhóm D — Dữ liệu sống**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| D1 | Thẻ | **"Dữ liệu trong database (live)"** — số dòng thực tế để đối chiếu với bản đã publish |

**Huy hiệu B1 là chỗ hợp đồng bốn vế hiện ra trên giao diện.** Nó **không** hiển
thị "hợp lệ / không hợp lệ" mà hiển thị **`signed: {tên khoá}`** — tức *"ai ký"* là
một phần của kết quả. Trạng thái **"chữ ký lạ"** phân biệt được kịch bản nguy hiểm
nhất: kẻ tấn công dựng dữ liệu khác, tính mã băm đúng, viết bản kê đúng, rồi **tự
ký bằng khoá của hắn** — chữ ký ấy hợp lệ về mật mã nhưng **thẩm quyền sai**.

**Thẻ B2 nói ra một luật thiết kế: thẩm quyền ký gắn với MÁY, không gắn với
người.** Chỉ máy có khoá riêng mới là **"Máy ghi"**; mọi máy khác là
**"Read-only"**.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `sot_authorized_keys` | X | X *(`revoked_at`)* | | X |
| 2 | `registry_versions` | X | | | X |
| 3 | `community_versions` | | | | X |
| 4 | Bản kê + chữ ký trên kho ngoài | X | | | X |
| 5 | `schema_migrations` | | | | X |
| 6 | `audit_log` | X | | | |

### Tiến trình — công bố (chỉ trên máy phát hành)

```
Dựng tạo tác ──► tính SHA-256 từng tệp ──► viết bản kê ──► ký bản kê (Ed25519)
                                                              │
                                                    đẩy lên kho lưu trữ ngoài
```

### Tiến trình — xác minh (mọi máy khác, lúc khởi động qua `sot-init`)

```
Kéo bản công bố
   ├─ tính lại mã băm, đối chiếu bản kê      → lệch  ⇒ DỪNG (mã thoát chuyên biệt)
   ├─ kiểm chữ ký phủ bản kê                 → hỏng  ⇒ DỪNG
   ├─ tra khoá ký trong danh sách tin cậy    → lạ    ⇒ DỪNG
   └─ hợp nhất theo nguyên tắc CHỈ ĐIỀN, KHÔNG XOÁ
```

**Mã thoát chuyên biệt của `sot-init` chặn toàn bộ hệ thống khởi động.** Đây là
quyết định có chủ ý, không phải hiệu ứng phụ: một máy không xác thực được danh mục
thì **không được phép phục vụ**. Thiết kế fail-closed ở đây trả giá bằng khả năng
sẵn sàng để đổi lấy khả năng **không phục vụ dữ liệu sai**.

### Ràng buộc

* **BR-7.1** thẩm quyền ký gắn với **máy**
* **BR-7.2** `Tạo tác hợp lệ = Toàn vẹn ∧ Chữ ký hợp lệ ∧ Người ký được tin cậy ∧ Chính sách phiên bản hợp lệ`
* **BR-7.3** xác minh trả về **tên khoá đã đăng ký**, không trả boolean
* **BR-7.4** không xác minh được ⇒ **DỪNG**
* **BR-7.5** hợp nhất **chỉ điền, không xoá**
* **BR-7.6 · GIỚI HẠN:** đơn điệu phiên bản **chưa được cưỡng chế** — bản công bố
  cũ hơn vẫn được chấp nhận (ca S7 của ma trận giả mạo). Tài nguyên mới không bị
  xoá, nhưng **giá trị dùng chung bị ghi đè lùi**

**Một bài học thiết kế đã trả giá:** danh sách cột bắt buộc dùng để kiểm bản công
bố từng **thiếu sáu cột**, nên một bản công bố có lược đồ thiếu vẫn **qua được khâu
xác minh** rồi mới hỏng giữa chừng lúc nhập dữ liệu. Đây là lý do phép đo phải
chạy qua **đúng đường tiêu thụ của ứng dụng**, không qua hàm trợ giúp.

---

## CN7.2 — Giám sát tài nguyên máy chủ (UC703)

### Mục đích

Nhìn thấy tình trạng CPU · RAM · GPU · ổ đĩa trên **một máy chủ duy nhất** chạy 14
dịch vụ — nơi một dịch vụ rò bộ nhớ kéo cả máy xuống.

### Giao diện 1 — Giám sát tài nguyên (`/admin/resources`, `AdminResourcesPage.tsx`, 557 dòng)

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| 1 | Tiêu đề | **"Giám sát tài nguyên"** — *"Tình trạng CPU · RAM · GPU · Ổ cứng và cấu hình phân phối tài nguyên hệ thống"* |
| 2 | Công tắc cập nhật | **"Trực tiếp"** / **"Tạm dừng"** |
| 3 | Thẻ chỉ số | CPU — **"{n} nhân logic"** |
| 4 | Thẻ chỉ số | **"RAM hệ thống"** — *"Bộ nhớ khả dụng cho Docker"* |
| 5 | Thẻ chỉ số | **"VRAM GPU (toàn máy)"** — *"Gồm cả Windows · VOYA: {n} tiến trình"* hoặc **"Không có số liệu"** |
| 6 | Thẻ chỉ số | **"Tải GPU"** — *"Nhiệt độ {n}°C · Công suất {n} W · {n} tiến trình"* |
| 7 | Thẻ chỉ số | **"Ổ cứng (Dataset)"** — *"Còn trống {n} GB"* hoặc **"Không đọc được"** |
| 8 | Biểu đồ | **"CPU theo nhân"** — *"{n} nhân · dùng chung, không ghim cứng"*; gợi ý từng cột: "Nhân {i}: {n}%" |
| 9 | Banner bình thường | **"Tài nguyên bình thường — không có cảnh báo"** |
| 10 | Nút | **"Bỏ qua"** — tắt báo động cho một phần cứng |
| 11 | Hộp thoại xác nhận | *"Bạn có chắc muốn tắt báo động cho phần cứng này không? Hành động này sẽ đánh dấu lỗi thành bỏ qua."* |
| 12 | Màn chờ | "Đang tải số liệu tài nguyên..." |

**Thẻ số 5 nói rõ một chi tiết dễ đọc sai: "VRAM GPU (toàn máy)" gồm cả phần của
hệ điều hành**, không phải chỉ của hệ thống này. Kèm theo là số tiến trình của
VOYA, để phân biệt *"GPU đầy vì ta"* với *"GPU đầy vì máy đang chạy thứ khác"*.

**Thẻ số 7 và số 5 dùng "Không đọc được" / "Không có số liệu" thay vì hiện số 0.**
Đây là cùng nguyên tắc với giá trị `-1` trong chỉ số: *"không đo được"* khác hẳn
*"đo được và bằng không"*.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | Chỉ số hệ thống (đọc trực tiếp) | | | | X |
| 2 | `platform_settings` *(cờ bỏ qua báo động)* | X | X | | X |
| 3 | Cấu hình `mem_limits` trong tệp compose | | | | X |

### Ràng buộc

* **RB-T1** một máy chủ 6 nhân / 12 GB / 1 GPU — **bắt buộc** đặt hạn mức bộ nhớ
  cho từng container
* CPU **dùng chung, không ghim cứng** cho từng dịch vụ (ghi rõ ở thành phần số 8)
* Nút "Bỏ qua" (số 10) là **cách hợp thức hoá một cảnh báo giả**, không phải cách
  sửa lỗi — hộp thoại nói đúng như vậy

---

## CN7.3 — Đối soát hai mặt phẳng lưu trữ (UC704)

### Mục đích

Giữ **nguồn sự thật tệp** và **bản sao truy vấn trong cơ sở dữ liệu** không lệch
nhau — hệ quả bắt buộc của ràng buộc RB-D2.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `dataset/samples.csv` | X | X | | X |
| 2 | `samples` | X | X | | X |
| 3 | `google_sheets_sync_status` | | X | | X |
| 4 | Kho ngoài (Drive + Sheets) | X | X | | X |

### Tiến trình

1. Tác vụ theo lịch (`celery-beat`) chạy đối soát theo chiều **CSV → cơ sở dữ liệu**.
2. Dòng có trong CSV mà thiếu trong CSDL được điền bù.
3. Dòng thiếu `storage_key` (chưa đẩy lên kho ngoài thành công) được điền về sau.
4. Trạng thái phản chiếu sang bảng tính ghi vào `google_sheets_sync_status`.

### Ràng buộc

* **NFR-R5** phải có **cơ chế đối soát định kỳ**
* Bản xuất sang bảng tính **giữ lại dòng đã xoá mềm** kèm dấu `deleted_at`, **không
  dịch dòng** — dịch dòng làm mọi tham chiếu theo số hàng sai (BR-5.9)
* Đường ghi tệp **không** chịu chính sách bảo mật mức hàng; cách ly ở mặt phẳng này
  dựa vào **cấu trúc thư mục theo tổ chức** cộng kiểm tra ở tầng ứng dụng — **mức
  bảo đảm thấp hơn** mặt phẳng CSDL (BR-2.7)

**Bốn bẫy làm việc đồng bộ CSV ↔ CSDL thất bại trong im lặng** đã gặp trong thực
tế; chúng là lý do bước đối soát phải kiểm **hậu điều kiện** chứ không chỉ chạy
xong là coi như xong.

---

## CN7.4 — Sao lưu và diễn tập khôi phục (UC705)

### Mục đích

Bảo đảm có đường quay lại khi dữ liệu hỏng — và bảo đảm **đường đó đã được thử**.

### Công cụ (chạy trên dòng lệnh)

```bash
sh scripts/pg_backup.sh                 # sao lưu
sh scripts/pg_backup.sh --drill         # diễn tập khôi phục vào CSDL tạm
```

### Ràng buộc — ba chi tiết bắt buộc, mỗi cái từ một lần sai

* **Thứ tự thao tác: kết xuất trước, nén sau.** Đảo thứ tự sinh ra tệp trông hợp lệ
  nhưng **thiếu phần đuôi**.
* **Kiểm toàn vẹn phải đọc hết nội dung.** Lệnh liệt kê nội dung tệp sao lưu
  (`pg_restore --list`) **không** phát hiện được tệp bị cụt — nó chỉ đọc phần mục lục.
* **Nhiều bản, nhiều nơi.** Cơ chế mã hoá và sao chép sang ổ khác **đã có, mặc định
  tắt**; phải bật khi triển khai thật.

**Nguyên tắc nền: *một bản sao lưu chưa được diễn tập khôi phục là một bản sao lưu
chưa tồn tại*** (BR-10.6).

**Một sự thật phải ghi lại:** tại thời điểm rà soát ngày 08/08/2026, cơ chế sao
lưu tự động **chưa từng chạy** — cơ chế có, lịch có, nhưng không có bản sao lưu
nào được sinh ra. Đây đúng là kiểu hỏng mà nguyên tắc trên tồn tại để bắt.

---

## CN7.5 — Kiểm chứng độ tươi triển khai và di trú lược đồ (UC706)

### Mục đích

Trả lời câu hỏi mà lệnh liệt kê container **không** trả lời được: *"mã đang chạy có
đúng là mã bạn vừa dựng không?"*

### Công cụ (chạy trên dòng lệnh)

| Kịch bản | Công dụng |
|---|---|
| `scripts/deploy.sh` | Triển khai, **tự dò GPU** |
| `scripts/check_deploy_freshness.py` | Phát hiện mã đang chạy lệch mã nguồn — bắt **ba kiểu lệch** |
| `python -m app.cli.migrate` | Di trú lược đồ, có **chốt chặn đích đến** |
| `scripts/run_tests.sh` | Chạy bộ kiểm thử đúng môi trường |
| `scripts/docker_gc.sh` | Dọn ảnh và lớp không dùng |

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/health` | Trạng thái từng thành phần |

### Tiến trình — cổng trước khi triển khai

```
1. Bộ kiểm thử dịch vụ         → 0 đỏ, và sổ dấu vết báo 0 hàng còn sót
2. Bộ kiểm thử + kiểm kiểu giao diện (npm run typecheck)
3. Nợ lược đồ                  → rỗng sau BA lần khởi động liên tiếp
4. Kiểm chứng độ tươi triển khai
```

### Ràng buộc

* **BR-10.1** bước tự động lúc khởi động **chỉ được thêm**; thay đổi một chiều phải
  qua lệnh di trú tường minh
* **BR-10.2** backend **từ chối khởi động** khi phiên bản lược đồ lệch, **cả hai
  chiều** — một dịch vụ cũ chạy trên lược đồ mới sẽ ghi dữ liệu thiếu cột
* **BR-10.3** lệnh di trú bắt buộc khai `EXPECTED_DATABASE`; chốt này sinh ra từ sự
  cố **13/08/2026**, khi biến `POSTGRES_DB` **không tham gia dựng chuỗi kết nối** và
  một lượt chạy đi nhầm vào cơ sở dữ liệu sản xuất
* **BR-10.5** nợ lược đồ phải rỗng sau **ba** lần khởi động liên tiếp — ba lần chứ
  không phải một, vì có loại chênh lệch chỉ lộ ra ở lần thứ hai hoặc thứ ba
* **NFR-M4** kiểm cả hai chiều phiên bản

**Ba bẫy của môi trường container, và lý do các công cụ trên tồn tại:**

1. **Trạng thái khoẻ mạnh ≠ mã mới.** Một ảnh giao diện từng chạy **sau mã nguồn
   năm tiếng** trong khi toàn bộ container báo khoẻ mạnh. Thêm nữa: **một ảnh
   container chống lưng cho năm dịch vụ** — dựng lại ảnh mà chỉ khởi động lại một
   dịch vụ thì bốn dịch vụ còn lại vẫn chạy mã cũ, hay quên nhất là bộ lập lịch.
2. **Đổi cấu hình không tự có hiệu lực.** Biến môi trường nạp lúc **tạo** container,
   không phải lúc khởi động → phải tạo lại container.
3. **Mất cấu hình chồng lớp.** Lệnh điều phối **trần** đánh rơi lớp GPU; hệ thống
   vẫn chạy, chỉ **không còn GPU**, và không báo gì. Vá bằng `COMPOSE_FILE` trong
   `.env`.

---

## Tổng kết ma trận chức năng ↔ use case của Nghiệp vụ 7

| Chức năng | Use case phủ | Nơi thực hiện |
|---|---|---|
| CN7.1 Nguồn sự thật và máy được cấp quyền | UC701, UC702 | `/admin/sot` + `sot-init` |
| CN7.2 Giám sát tài nguyên | UC703 | `/admin/resources` |
| CN7.3 Đối soát hai mặt phẳng lưu trữ | UC704 | tác vụ theo lịch |
| CN7.4 Sao lưu và diễn tập khôi phục | UC705 | dòng lệnh |
| CN7.5 Độ tươi triển khai và di trú lược đồ | UC706 | dòng lệnh + `/health` |

**Bốn trong sáu use case chạy ngoài ứng dụng.** Đó là lý do tác nhân A10 được đánh
dấu 🟡 ở bảng tác nhân: ranh giới thật của họ là **quyền hệ điều hành**, không phải
một vai trong hệ thống.
