# 10.3 Thiết kế chi tiết — Nghiệp vụ 3: Danh mục từ vựng và phương ngữ

***10 use case** (UC301–UC310) cài đặt trên **22 điểm cuối** của hai bộ định tuyến
`classes` và `vocabulary`.*

Nghiệp vụ này trả lời một câu: **được phép thu lớp nào, theo phương ngữ nào?** Nó
là chỗ mô hình **ba mặt phẳng danh mục** hiện ra thành thao tác thật, và là chỗ
luật **không-rơi-ngược** được cưỡng chế.

```
Danh mục hệ thống ──sao chép MỘT LẦN──► Danh mục của tổ chức ──ghim──► Bộ dữ liệu
 (quản trị nền tảng)                     (tổ chức tự sửa)             (bất biến, có mã băm)
```

---

## CN3.1 — Đọc danh mục hiện hành (UC301, UC302)

### Mục đích

Cho mọi màn hình cần danh mục — thu mẫu, huấn luyện, nhận dạng — đọc **cùng một
nguồn**, kèm số hiệu phiên bản, để không nơi nào tự dựng lấy một danh sách riêng.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/api/v1/vocabulary/registry` | Toàn bộ danh mục: phiên bản, phương ngữ, hồ sơ nhận diện |
| `GET` | `/classes/list` | Danh sách lớp trong phạm vi tổ chức |
| `GET` | `/classes/community-stats` | Thống kê mặt phẳng cộng đồng |

### Giao diện

Danh mục **không có màn hình riêng cho người dùng thường** — nó xuất hiện dưới
dạng hộp chọn ngôn ngữ / phương ngữ trong màn hình thu (CN2.1 nhóm B), bộ lọc
trong thư viện nhãn (CN2.4 nhóm B), và bộ chọn phương ngữ ở bước huấn luyện
(CN4.2). Màn hình quản trị danh mục là CN3.3.

**Dòng tóm tắt xuất hiện ở màn hình thu** làm cầu nối giữa hai nơi:
**"{ngôn ngữ} / {phương ngữ} • {n} nhãn"**.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `vocabulary_registry_meta` | | | | X |
| 2 | `registry_versions` | | | | X |
| 3 | `dialects` | | | | X |
| 4 | `recognition_profiles` | | | | X |
| 5 | `vocabulary_groups` | | | | X |
| 6 | `languages` · `regions` | | | | X |
| 7 | `classes` | | | | X |

### Tiến trình

1. Máy khách gọi `GET /api/v1/vocabulary/registry`.
2. Máy chủ trả danh mục **của tổ chức đang đăng nhập**, kèm số hiệu phiên bản
   hiện hành.
3. Màn hình dựng hộp chọn từ dữ liệu nhận được — **không có danh sách gắn cứng
   trong mã**.

### Luồng ngoại lệ

1. **Không tải được danh mục.** Màn hình thu hiện *"Không tải được danh sách bộ
   ngôn ngữ từ máy chủ."* và **không cho thu tiếp**. Hệ thống **không** rơi về một
   danh sách mặc định.

### Ràng buộc

* **BR-4.3** lúc chạy **KHÔNG bao giờ rơi ngược** về mặt phẳng cộng đồng; thiếu dữ
  liệu thì **dừng**, không suy đoán
* **BR-2.1** danh mục trả về đã bị lọc theo tổ chức ở tầng CSDL

**Ba lỗi có thật đã thúc đẩy thiết kế này**, và cả ba đáng ghi lại vì chúng giải
thích vì sao danh mục không được phép là một danh sách trong mã:

1. Danh sách hồ sơ nhận dạng **gắn cứng ở hai nơi** trong mã và **đã lệch nhau**
   (6 mục so với 5) → **7 lớp bị loại khỏi bước chia dữ liệu trong im lặng**.
2. Số hiệu phiên bản danh mục là một **bộ đếm bị ghi đè**, và ảnh chụp là một
   **tệp bị ghi đè** → *"bộ dữ liệu ghim phiên bản 2"* **không thực hiện được**, vì
   nội dung phiên bản 2 biến mất ngay khi phiên bản 3 được ghi.
3. Không có khái niệm thành viên tổ chức → hoặc không tổ chức nào tự quản được,
   hoặc mọi quản trị viên nền tảng thành biên tập viên của mọi tổ chức.

---

## CN3.2 — Đề xuất phương ngữ mới (UC303)

### Mục đích

Cho người đang thu dữ liệu **dùng được ngay** một phương ngữ chưa có trong danh
mục, mà không phải chờ quản trị viên — nhưng vẫn để lại một đề xuất cần duyệt, để
danh mục không trôi thành một danh sách tự do.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `POST` | `/api/v1/vocabulary/dialects` | Tạo đề xuất phương ngữ (mã 201) |

### Giao diện 1 — Đề xuất phương ngữ mới (`AddDialectModal.tsx`)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề hộp thoại | — | **"Đề xuất phương ngữ mới"** |
| 2 | Ghi chú cơ chế | — | **"Bạn dùng được ngay, quản trị viên sẽ duyệt sau."** |
| 3 | Ô nhập | rỗng | **"Tên phương ngữ"**, gợi ý "Ví dụ: Cần Thơ, Miền núi, v.v." |
| 4 | Xem trước mã | — | **"Mã sẽ tạo:"** + mã suy ra từ tên |
| 5 | Cảnh báo trùng | ẩn | **"Mã `{id}` đã tồn tại"** |
| 6 | Nút gợi ý | ẩn | **"Dùng phương ngữ có sẵn này"** |
| 7 | Nút huỷ | — | **"Hủy"** |

**Thành phần 4 và 6 cùng giải một bài toán:** người dùng gõ tên tự do, hệ thống
suy ra mã, và **nếu mã đó đã tồn tại thì đề nghị dùng lại phương ngữ có sẵn** thay
vì tạo một bản trùng. Đây là cơ chế chống phân mảnh danh mục ngay tại điểm nhập,
rẻ hơn nhiều so với gộp thủ công về sau.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `dialects` | X *(trạng thái chờ duyệt)* | | | X |
| 2 | `audit_log` | X | | | |

### Tiến trình

1. Người dùng mở hộp thoại từ hộp chọn phương ngữ (mục **"+ Thêm mới..."**).
2. Gõ tên; hệ thống hiện **mã sẽ tạo** theo thời gian thực.
3. Nếu mã đã tồn tại → hiện cảnh báo và nút dùng lại phương ngữ có sẵn.
4. Gửi đề xuất → phương ngữ được tạo ở **trạng thái chờ duyệt** và **dùng được
   ngay**.
5. Đề xuất xuất hiện trong hàng chờ của quản trị viên (CN3.3).

### Ràng buộc

* **BR-4.1** phương ngữ tham gia vào **định danh lớp**, nên tạo một phương ngữ
  trùng nghĩa nhưng khác mã sẽ **tách một lớp thành hai** — đó là lý do bước 3 tồn tại
* Phương ngữ chờ duyệt vẫn thuộc **danh mục của tổ chức**, không phải mặt phẳng
  cộng đồng

---

## CN3.3 — Duyệt, gộp và quản lý phương ngữ (UC304, UC305, UC306)

### Mục đích

Giữ danh mục sạch mà **không làm mồ côi dữ liệu đã gắn mã cũ**.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/api/v1/vocabulary/dialects/pending` | Hàng chờ duyệt |
| `POST` | `/api/v1/vocabulary/dialects/{id}/approve` | Duyệt |
| `POST` | `/api/v1/vocabulary/dialects/{id}/reject` | Từ chối **kèm nơi gộp** |
| `PATCH` | `/api/v1/vocabulary/dialects/{id}` | Đổi tên hiển thị, bật/tắt |
| `GET` | `/api/v1/vocabulary/registry` | Đọc danh mục hiện hành |

### Giao diện 1 — Từ vựng & phương ngữ (`/admin/vocabulary`, `AdminVocabularyPage.tsx`, 401 dòng)

**Nhóm A — Đầu trang**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| A1 | Tiêu đề | **"Từ vựng & phương ngữ"** |
| A2 | Phụ đề | **"Registry phiên bản {ver} · {n} phương ngữ · {m} hồ sơ nhận diện"** |

**Nhóm B — Hàng chờ duyệt**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| B1 | Tiêu đề khối | **"Chờ duyệt"** |
| B2 | Trạng thái rỗng | **"Không có đề xuất nào đang chờ."** |
| B3 | Dòng xuất xứ | **"Đề xuất bởi {ai} · {lúc}"** |
| B4 | Nút | **"Duyệt"** |
| B5 | Hộp chọn nơi gộp | **"Từ chối, gộp vào"** — mục rỗng: **"— chọn phương ngữ —"** |
| B6 | Nút | **"Từ chối"** |
| B7 | **Ghi chú ràng buộc** | *"Từ chối bắt buộc chọn nơi gộp — dữ liệu đã gắn mã này sẽ chuyển sang đó thay vì mồ côi."* |

**Nhóm C — Bảng phương ngữ**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| C1 | Bộ lọc | **"Tất cả phương ngữ"** |
| C2 | Cột bảng | **"Mã"** · **"Tên hiển thị"** · **"Trạng thái"** · **"Thao tác"** |
| C3 | Huy hiệu trạng thái | **"đang bật"** / **"đã tắt"** |
| C4 | Nút | **"Đổi tên"** → **"Lưu"** / **"Hủy"** |
| C5 | Nút | **"Bật"** / **"Tắt"** |

**Nhóm D — Hồ sơ nhận diện**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| D1 | Tiêu đề khối | **"Hồ sơ nhận diện"** |
| D2 | **Ghi chú thứ tự** | *"Thứ tự do máy chủ quyết định (theo địa lý, không theo bảng chữ cái) — hiển thị đúng thứ tự nhận được, không sắp xếp lại."* |
| D3 | Nhãn phụ | **"(không huấn luyện)"** — hồ sơ có nhưng không dùng để huấn luyện |

**Thông báo kết quả:** *"Đã duyệt {id}"* · *"Đã từ chối {id}, gộp vào {đích}"* ·
*"Đã đổi tên hiển thị của {id}"* · *"Đã bật {id}"* / *"Đã tắt {id}"*.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `dialects` | | X *(duyệt / đổi tên / bật tắt / `merged_into`)* | | X |
| 2 | `dialect_aliases` | X *(khi gộp)* | | | X |
| 3 | `samples` | | X *(chuyển mã phương ngữ)* | | X |
| 4 | `classes` | | X | | X |
| 5 | `recognition_profiles` | | | | X |
| 6 | `registry_versions` | X | | | X |
| 7 | `audit_log` | X | | | |

### Tiến trình — duyệt một đề xuất

1. Quản trị viên mở hàng chờ.
2. Bấm **"Duyệt"** → phương ngữ chuyển sang trạng thái chính thức.
3. Hệ thống ghi một **phiên bản danh mục mới** và ghi kiểm toán.

### Tiến trình — từ chối và gộp

1. Quản trị viên chọn **nơi gộp** trong hộp chọn B5. **Không chọn thì không từ
   chối được** — đây là ràng buộc bắt buộc, không phải trường tuỳ chọn.
2. Bấm **"Từ chối"**.
3. Hệ thống ghi một bí danh trỏ mã cũ sang mã đích, và **chuyển mọi dữ liệu đã
   gắn mã cũ sang mã đích**.
4. Thông báo nêu **cả hai mã**: *"Đã từ chối {id}, gộp vào {đích}"*.

**Vì sao ràng buộc ở bước 1 tồn tại:** một phương ngữ bị từ chối mà không nêu nơi
gộp sẽ để lại các mẫu trỏ tới một mã không còn hợp lệ. Với khoá ngoại ghép mang
định danh tổ chức, điều đó **hỏng ở tầng ràng buộc** chứ không hỏng lặng lẽ — nên
giao diện chặn trước, ở đúng chỗ người dùng đang thao tác.

### Tiến trình — bật / tắt một phương ngữ

Tắt một phương ngữ **không xoá** nó và không đụng tới dữ liệu đã gắn; nó chỉ ẩn
khỏi các hộp chọn ở màn hình thu. Đây là cách rút một phương ngữ khỏi vòng dùng mà
vẫn giữ được ý nghĩa của dữ liệu lịch sử.

### Ràng buộc

* **BR-4.1** phương ngữ là một phần định danh lớp
* Từ chối **bắt buộc** nêu nơi gộp
* Mọi thay đổi danh mục sinh một **phiên bản mới**, không ghi đè phiên bản cũ
  (BR-4.4)
* **D2 — thứ tự hiển thị do máy chủ quyết định.** Giao diện **không được sắp xếp
  lại**: thứ tự địa lý mang thông tin mà thứ tự bảng chữ cái làm mất

---

## CN3.4 — Phiên bản danh mục và ghim phiên bản (UC307, UC308)

### Mục đích

Làm cho một bộ dữ liệu **ghim được** vào một trạng thái danh mục xác định, để hai
lần chạy huấn luyện cách nhau một tháng trên "cùng một bộ dữ liệu" thật sự chạy
trên **cùng một tập nhãn**.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `registry_versions` | X | | | X |
| 2 | `vocabulary_registry_meta` | | X *(phiên bản hiện hành)* | | X |
| 3 | `training_jobs` | | X *(cột `registry_version`)* | | X |

### Tiến trình

1. Mỗi thay đổi danh mục được duyệt sinh một hàng mới trong `registry_versions`,
   mang **ảnh chụp bất biến** và **mã băm nội dung**.
2. `vocabulary_registry_meta` trỏ tới phiên bản hiện hành.
3. Khi một tác vụ huấn luyện được tạo, số hiệu phiên bản được **chép vào bản ghi
   tác vụ** — qua khoá ngoại ghép
   `training_jobs(tenant_id, registry_version) → registry_versions(tenant_id, version)`.
4. Chạy lại tác vụ sáu tháng sau vẫn dùng **đúng tập nhãn của lần đầu**.

### Ràng buộc

* **BR-4.4** phiên bản danh mục là ảnh chụp **bất biến**
* **BR-4.5** quan hệ tác vụ ↔ phiên bản là quan hệ **ghim**, không phải tham chiếu
  tới trạng thái hiện tại
* Tại ảnh chụp 10/08/2026, `registry_versions` có **89 hàng** — tức danh mục đã
  qua 89 lần thay đổi được ghi nhận

---

## CN3.5 — Ba mặt phẳng danh mục và luật không-rơi-ngược (UC309, UC310)

### Mục đích

Giữ ranh giới giữa **danh mục hệ thống**, **danh mục của tổ chức** và **ảnh chụp
bất biến** — ba thứ trông giống nhau trên sơ đồ nhưng khác hẳn nhau về quyền sửa
và về hệ quả khi sai.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn | RLS |
|:--:|---|:--:|:--:|:--:|:--:|:--:|
| 1 | `community_dialects` | | | | X | — |
| 2 | `community_profiles` | | | | X | — |
| 3 | `community_versions` | | | | X | — |
| 4 | `dialects` (của tổ chức) | X | X | | X | ✔ |
| 5 | `recognition_profiles` (của tổ chức) | X | X | | X | ✔ |
| 6 | `registry_versions` | X | | | X | ✔ |

**Ba bảng `community_*` cố ý KHÔNG bật chính sách bảo mật mức hàng**, vì chúng là
mặt phẳng đọc chung. Điều này an toàn **chỉ vì** luật không-rơi-ngược được cưỡng
chế ở tầng ứng dụng: dữ liệu chảy từ mặt phẳng cộng đồng sang tổ chức **đúng một
lần, lúc khởi tạo**, và **không có đường ngược lại lúc chạy**.

### Tiến trình — khởi tạo danh mục cho tổ chức mới

1. Tổ chức mới được tạo.
2. Hệ thống **sao chép một lần** danh mục cộng đồng sang danh mục của tổ chức.
3. Từ thời điểm đó, tổ chức tự sửa danh mục của mình; sửa của tổ chức **không**
   ảnh hưởng mặt phẳng cộng đồng, và ngược lại.

### Ràng buộc

* **BR-4.2** sao chép **một lần, lúc khởi tạo** — đây là **kế thừa**
* **BR-4.3** đọc danh mục cộng đồng khi tổ chức thiếu dữ liệu là **rơi về**, và
  **bị cấm**
* **BR-8.6** giá trị `default` **không phải** mặt phẳng cộng đồng — nó là một tổ
  chức bình thường về mọi mặt cách ly, nơi dữ liệu lịch sử nằm lại

**Một cái bẫy cụ thể trong mã, ghi lại vì nó tạo ra mã chết:** hàm chuẩn hoá định
danh tổ chức **trả về `default` khi nhận chuỗi rỗng**. Một hàm kiểm tra viết **sau**
bước chuẩn hoá sẽ **không bao giờ thấy chuỗi rỗng**. Nguyên tắc: *kiểm tham số thô
trước khi chuẩn hoá*.

---

## CN3.6 — Phân biệt "đã đăng ký" với "huấn luyện được"

Đây không phải một màn hình mà là **một luật phải giữ nhất quán trên nhiều màn
hình**, nên ghi thành mục riêng.

| Câu hỏi | Trả lời ở đâu | Điều kiện |
|---|---|---|
| Lớp này **có trong danh mục** không? | `/labels` | Có hàng trong `classes` |
| Lớp này **đủ mẫu để huấn luyện** chưa? | Thẻ nhãn — *"Cần thêm {n} lần quay"* / *"Đã đủ điều kiện huấn luyện"* | Số lần quay ≥ sàn |
| Lớp này **phát hành được cho nghiên cứu** không? | Cổng đồng thuận lúc chọn mẫu (CN4.5) | Người ký đã đồng ý ở mức tương ứng |

**Ba câu hỏi khác nhau, và trả lời "có" ở hai câu đầu không kéo theo "có" ở câu
thứ ba.** Một lớp đủ mẫu nhưng người ký chưa đồng ý ở mức tương ứng thì với đường
phát hành nghiên cứu, **nó là một lớp rỗng** (BR-4.7).

Nhãn **"Đã đủ điều kiện huấn luyện"** trên thẻ nhãn ở `/labels` vì thế phải đọc
đúng mức: nó nói về **số lượng**, không nói về đồng thuận.

---

## Tổng kết ma trận chức năng ↔ use case của Nghiệp vụ 3

| Chức năng | Use case phủ | Màn hình chính |
|---|---|---|
| CN3.1 Đọc danh mục hiện hành | UC301, UC302 | nội tuyến (hộp chọn ở nhiều màn hình) |
| CN3.2 Đề xuất phương ngữ mới | UC303 | `AddDialectModal` |
| CN3.3 Duyệt, gộp, quản lý phương ngữ | UC304, UC305, UC306 | `/admin/vocabulary` |
| CN3.4 Phiên bản danh mục và ghim | UC307, UC308 | nội tuyến |
| CN3.5 Ba mặt phẳng danh mục | UC309, UC310 | nội tuyến |
| CN3.6 "Đã đăng ký" ≠ "huấn luyện được" | — (luật xuyên màn hình) | — |
