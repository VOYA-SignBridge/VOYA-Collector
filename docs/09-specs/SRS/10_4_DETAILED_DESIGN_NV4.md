# 10.4 Thiết kế chi tiết — Nghiệp vụ 4: Huấn luyện, đánh giá và suy luận

***9 use case** (UC401–UC409) cài đặt trên **20 điểm cuối gọi được** của bốn bộ
định tuyến `training` (13), `inference` (1), `realtime_proxy` (3), `tts` (3).*

> **Đính chính (18/08/2026).** Bản trước của dòng này đếm cả bộ định tuyến
> `experiments` (12 điểm cuối) và ra con số 31. Con số đó **sai**: `experiments`
> **không được `include_router`** trong [main.py](../../../backend/app/main.py) —
> 12 điểm cuối ấy **không có URL nào gọi tới được**. Chúng được kể ở §10.4.9 như
> một *thiết kế chưa mount*, không phải chức năng đang chạy.

Đây là chỗ dữ liệu thành sản phẩm. Giao diện tự mô tả là **"Quy trình 7 bước để
huấn luyện mô hình nhận diện ký hiệu với hiệu suất tối ưu"**, và mỗi bước là một
màn hình con trong `pages/training/`.

**Phạm vi phải khoanh trước:** luận văn **không đánh giá độ chính xác mô hình**.
Các chỉ số trong nghiệp vụ này là **đầu ra của một lượt chạy**, không phải kết quả
của một phép đánh giá hệ thống.

---

## CN4.1 — Xem thông tin bộ dữ liệu (UC401)

### Mục đích

Cho người chạy huấn luyện thấy **dữ liệu họ sắp dùng trông thế nào** trước khi
tiêu tài nguyên GPU — đặc biệt là mức mất cân bằng giữa các lớp.

### Điểm cuối API

| Phương thức | Đường dẫn | Vai trò |
|---|---|---|
| `GET` | `/api/v1/training/dataset-info` | Tổng mẫu, số lớp, ngôn ngữ, phương ngữ, phân bố lớp |

### Giao diện 1 — Thống kê bộ dữ liệu (`DatasetInfo.tsx`, 168 dòng)

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| 1 | Tiêu đề khối | **"Thống Kê Chính"** |
| 2 | Thẻ chỉ số | **"Tổng mẫu"** (đơn vị: video) |
| 3 | Thẻ chỉ số | **"Số lớp"** (đơn vị: ký hiệu) |
| 4 | Thẻ chỉ số | **"Ngôn ngữ"** |
| 5 | Thẻ chỉ số | **"Phương ngữ"** |
| 6 | Biểu đồ | **"Phân Bố Theo Phương Ngữ"** + "{n} phương ngữ" |
| 7 | Biểu đồ | **"Phân Bố Lớp (Top 10)"** + **"Tổng: {n} mẫu"** |
| 8 | Banner sẵn sàng | **"Dữ liệu sẵn sàng"** + *"Dataset đã được tải thành công. Hãy tiếp tục để xem chi tiết phân chia tập dữ liệu."* |
| 9 | Màn chờ | "Đang tải thông tin dataset..." |
| 10 | Banner lỗi | **"Không thể tải dataset"** + *"Vui lòng kiểm tra xem folder dataset có tồn tại và chứa các file CSV cần thiết."* |

**Thành phần số 7 — "Phân Bố Lớp (Top 10)" — là chỗ mất cân bằng dữ liệu hiện
ra.** Trên kho dữ liệu hiện tại, **64 % là lớp bảng chữ cái**. Đây chính là lý do
luận văn không dùng độ chính xác mô hình làm chỉ số: một con số cao trên phân bố
này sẽ nói về **bộ dữ liệu** chứ không nói về hệ thống.

**Thông báo lỗi số 10 tiết lộ một sự thật kiến trúc:** nó nói tới *"folder dataset"*
và *"các file CSV"*. Nguồn dữ liệu ở bước này là **mặt phẳng tệp**, không phải cơ
sở dữ liệu — hệ quả trực tiếp của ràng buộc RB-D2.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `dataset/samples.csv` | | | | X |
| 2 | `samples` | | | | X |
| 3 | `classes` | | | | X |
| 4 | `dialects` · `languages` | | | | X |

### Ràng buộc

* **BR-2.7** đường đọc này chạm **mặt phẳng tệp**, nơi cách ly dựa vào cấu trúc
  thư mục cộng kiểm tra ở tầng ứng dụng — **mức bảo đảm thấp hơn** mặt phẳng CSDL
* Chính đường đọc này (`list_classes()` đọc `labels.csv` trên đĩa) là nguyên nhân
  làm **phép đo cách ly ngày 15/08/2026 bị loại**: fixture chỉ ghi vào PostgreSQL
  nên đối chứng dương không đạt

---

## CN4.2 — Chọn phương ngữ để huấn luyện (UC402)

### Mục đích

Cho người chạy quyết định **dữ liệu của phương ngữ nào** vào mô hình — vì trộn
phương ngữ là một quyết định nghiên cứu, không phải một mặc định kỹ thuật.

### Giao diện 1 — Chọn phương ngữ (`DialectSelector.tsx`, 301 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề | — | **"Chọn Phương Ngữ Để Huấn Luyện"** + *"Chọn một hoặc nhiều phương ngữ để bao gồm trong quá trình huấn luyện"* |
| 2 | Nhóm nút chế độ | Theo Vùng | **"Theo Vùng"** / **"Bảng Chữ Cái"** — nhãn trợ năng "Chế độ hiển thị" |
| 3 | Nút | — | **"Chọn tất cả ({n})"** |
| 4 | Nút | — | **"Bỏ chọn tất cả"** |
| 5 | Nhóm theo ngôn ngữ | — | **"{tổng} phương ngữ • {chọn} được chọn"** |
| 6 | Huy hiệu nhóm | — | **"Đã chọn hết"** hoặc **"◐ {n} mục"** |
| 7 | Cảnh báo chưa chọn | ẩn | **"Chưa chọn phương ngữ"** + *"Vui lòng chọn ít nhất một phương ngữ để có thể bắt đầu huấn luyện."* |
| 8 | Tóm tắt đã chọn | — | **"Đã chọn {n} phương ngữ"** + *"Mô hình sẽ được huấn luyện sử dụng các phương ngữ đã chọn."* |

**Thành phần số 2 cho hai cách sắp xếp cùng một danh sách**, và đây là một lựa
chọn có ý nghĩa: sắp theo **vùng** giữ được thông tin địa lý (phương ngữ gần nhau
về địa lý thường gần nhau về hình thái ký hiệu), sắp theo **bảng chữ cái** thì dễ
tìm. Cả hai đều cần, nên giao diện cho chuyển chứ không chọn hộ.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `dialects` | | | | X |
| 2 | `regions` · `languages` | | | | X |
| 3 | `samples` | | | | X *(đếm theo phương ngữ)* |

### Ràng buộc

* Không chọn phương ngữ nào ⇒ **không bắt đầu huấn luyện được**
* **Lựa chọn ở bước này bị bỏ qua** khi lần chạy dùng một split đã versioned —
  xem CN4.5, và giao diện nói rõ điều đó

---

## CN4.3 — Chia tập dữ liệu (UC403)

### Mục đích

Làm cho việc chia tập trở thành một quyết định **nhìn thấy được** thay vì một
hằng số giấu trong mã.

### Giao diện 1 — Điều chỉnh tỷ lệ chia tập (`DataSplitVisualization.tsx`, 248 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Dòng ngữ cảnh | — | **"Chia tập cho phương ngữ đã chọn:"** |
| 2 | Tiêu đề khối | — | **"Điều Chỉnh Tỷ Lệ Chia Tập"** |
| 3 | Thanh trượt | 70 % | **"Tập Huấn Luyện"** — *"{n} mẫu — dùng để dạy mô hình"* |
| 4 | Thanh trượt | 15 % | **"Tập Kiểm Tra (Validation)"** — *"{n} mẫu — dùng để điều chỉnh mô hình"* |
| 5 | Giá trị tính tự động | 15 % | **"Tập Đánh Giá (Test)"** — *"{n} mẫu — đo hiệu suất cuối cùng (tính tự động)"* |
| 6 | Biểu đồ | — | **"Hình Ảnh Phân Chia"** với ba dải: **"Train: {n} mẫu"** · **"Validation: {n} mẫu"** · **"Test: {n} mẫu"** |
| 7 | Ba thẻ giải thích | — | **"Huấn Luyện"** (Dạy mô hình) · **"Kiểm Tra"** (Điều chỉnh) · **"Đánh Giá"** (Kiểm định cuối) |
| 8 | Khối hướng dẫn | — | **"Hướng dẫn phân chia"** — "Train (70%): Dùng để huấn luyện mô hình" · "Validation (15%): Dùng để điều chỉnh hyperparameters" |

**Thành phần số 5 là giá trị phụ thuộc, không phải ô nhập thứ ba.** Tập đánh giá
được tính bằng phần còn lại, nên ba tỉ lệ **luôn cộng đúng 100 %** — không có
trạng thái người dùng nhập ba số không khớp nhau.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `samples` | | | | X |
| 2 | `classes` | | | | X |
| 3 | `training_job_classes` | X | | | |

### Ràng buộc — điểm quan trọng nhất của nghiệp vụ này

* **BR-6.2 — sàn số mẫu mỗi lớp phải áp TRƯỚC khi đánh chỉ số lớp.** Làm ngược thì
  chỉ số lớp **nhảy cóc**, và mô hình huấn luyện trên một không gian nhãn khác với
  không gian nhãn lúc suy luận — một lỗi **không sinh ra thông báo nào**, chỉ sinh
  ra kết quả sai.
* **BR-6.3 — lọc lúc chia tập ≠ từ chối lúc chạy.** *Lọc* là loại lớp không đủ điều
  kiện rồi **tiếp tục**; *từ chối* là **dừng cả tác vụ**. Hệ thống làm cả hai, ở hai
  chỗ khác nhau, và phải nói rõ chỗ nào làm gì — nếu không, người dùng sẽ tưởng mô
  hình được huấn luyện trên tập lớp mình chọn.
* **BR-6.4** `training_job_classes` lưu **tập lớp thực sự tham gia sau ba cổng**,
  không phải tập được chọn.

---

## CN4.4 — Tăng cường dữ liệu (UC404)

### Mục đích

Bù phần nào cho việc dữ liệu ít, bằng cách sinh biến thể từ mẫu gốc — và cho người
chạy **bật/tắt từng kỹ thuật** thay vì nhận một hộp đen.

### Giao diện 1 — Xem trước tăng cường (`AugmentationPreview.tsx`, 231 dòng)

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| 1 | Tiêu đề | — | **"Kỹ Thuật Tăng Cường Dữ Liệu"** + *"Tạo các biến thể từ dữ liệu gốc để mô hình học tổng quát hơn"* |
| 2 | Nút | — | **"Bật Hết"** |
| 3 | Nút | — | **"Tắt Hết"** |
| 4 | Chỉ báo | — | **"Đang sử dụng {n}/{tổng} kỹ thuật"** |
| 5 | Khối lợi ích | — | **"Lợi Ích Của Tăng Cường"** |
| 6 | Mục lợi ích | — | **"Tăng dữ liệu:"** *Mỗi mẫu gốc tạo ra ~10 biến thể mới* |
| 7 | Mục lợi ích | — | **"Cải thiện tổng quát:"** *Model học các đặc trưng cốt lõi thay vì ghi nhớ* |
| 8 | Mục lợi ích | — | **"Linh hoạt hơn:"** *Xử lý tốt hơn với góc độ, vị trí, kích thước khác nhau* |
| 9 | **Mục chi phí** | — | **"Tính toán:"** *Tăng thời gian huấn luyện ~ 20-30 % (vẫn chấp nhận được)* |

**Thành phần số 9 đáng nói riêng vì nó là chi phí, không phải lợi ích** — và giao
diện đặt nó **cùng danh sách** với ba lợi ích thay vì giấu đi. Một khối "lợi ích"
chỉ liệt kê lợi ích là một khối quảng cáo.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | Tệp `.npz` | | | | X |
| 2 | `training_jobs` (tham số) | | X | | X |

### Ràng buộc

* Hệ số tăng cường **khác nhau giữa mẫu thu trực tiếp và mẫu từ video tải lên**,
  và được ghi vào tham số của lượt chạy để về sau đối chiếu được
* Bản tăng cường **chia sẻ `session_id`** với mẫu gốc — đây là lý do thao tác đổi
  nhãn ở CN2.5 phải xử lý *"mẫu gốc plus mọi bản tăng cường cùng session_id"*

---

## CN4.5 — Cấu hình huấn luyện và ba cổng chặn (UC405)

### Mục đích

Chốt tham số cho một lượt chạy, và **áp ba cổng chặn** trước khi tiêu GPU.

### Giao diện 1 — Cấu hình huấn luyện (`TrainingSettings.tsx`, 395 dòng)

**Nhóm A — Chế độ chạy và split versioned**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| A1 | Tiêu đề | **"Chế độ chạy"** |
| A2 | Danh sách split | **"Split đã versioned"** |
| A3 | Dòng split | **"{bản} — {n} lớp · train {tr}/val {va}/test {te}"** |
| A4 | **Ghi chú ưu tiên** | *"Split đã định nghĩa sẵn tập dữ liệu, nên lựa chọn phương ngữ ở bước trước không áp dụng cho lần chạy này."* |
| A5 | Cảnh báo thiếu split | *"Chưa có split nào đủ điều kiện nghiên cứu (cần `valid_for_research`)"* |

**Nhóm B — Kiến trúc và siêu tham số**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| B1 | Tiêu đề | — | **"Chọn Mô Hình"** + *"Lựa chọn kiến trúc mạng neural cho huấn luyện"* |
| B2 | Tiêu đề | — | **"Cấu Hình Hyperparameters"** + *"Chọn cách bạn muốn cấu hình các thông số huấn luyện"* |
| B3 | Công tắc | bật | **"Dùng cấu hình mặc định"** |
| B4 | Nút | — | **"Tuỳ chỉnh cấu hình"** |
| B5 | Nhãn giá trị gốc | — | **"Mặc định: {giá trị}"** — hiện cạnh mỗi ô đã sửa |
| B6 | Nút | — | **"↻ Đặt Lại Cấu Hình Mặc Định"** |
| B7 | Ước lượng | — | **"Thời gian dự kiến"** — *"Với cấu hình hiện tại, quá trình huấn luyện sẽ mất khoảng **30-60 phút** tùy thuộc vào cấu hình phần cứng của máy."* |

**Nhóm A là phần quan trọng nhất của màn hình này, và nó nói ra một luật nghiệp
vụ ngay trên giao diện.** Khi lượt chạy dùng một **split đã versioned**, tập dữ
liệu đã được định nghĩa sẵn, nên **lựa chọn phương ngữ ở CN4.2 không áp dụng**.
Giao diện nói trước điều đó (A4) thay vì để người dùng phát hiện sau khi kết quả
không khớp với thứ họ đã chọn.

**Cờ `valid_for_research` (A5) là một cổng thật, không phải nhãn.** Không có split
nào đủ điều kiện thì đường chạy nghiên cứu **không mở**. Đây là hệ quả trực tiếp
của yêu cầu tái lập: một lượt chạy không ghim được tập dữ liệu thì kết quả của nó
không trích dẫn được.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `training_jobs` | X | X | | X |
| 2 | `training_job_classes` | X | | | X |
| 3 | `registry_versions` | | | | X |
| 4 | `signer_consents` | | | | X |
| 5 | `plans` · `tenant_subscriptions` | | | | X |
| 6 | `tenant_usage_daily` | X | X | | X |
| 7 | `samples` · `classes` | | | | X |

### Tiến trình — ba cổng chặn theo đúng thứ tự áp dụng

```
1. Chọn phạm vi dữ liệu và tham số
2. CỔNG 3 — hạn mức tổ chức, áp LÚC XẾP HÀNG
      → hết hạn mức ⇒ TỪ CHỐI cả tác vụ
3. GHIM phiên bản danh mục vào bản ghi tác vụ
4. CỔNG 1 — đồng thuận, áp LÚC CHỌN MẪU
      → mẫu không đủ mức đồng thuận KHÔNG XUẤT HIỆN trong tập
5. CỔNG 2 — sàn số mẫu mỗi lớp, áp TRƯỚC KHI ĐÁNH CHỈ SỐ LỚP
      → lớp không đủ mẫu bị LỌC ra, tác vụ VẪN TIẾP TỤC
6. Đánh chỉ số lớp trên tập lớp CÒN LẠI
7. Lưu training_job_classes = tập lớp THỰC SỰ THAM GIA
8. Xếp hàng cho dịch vụ `trainer`
```

| Cổng | Hỏi gì | Áp ở đâu | Hỏng thì hậu quả |
|---|---|---|---|
| Đồng thuận | Người ký cho phép dùng ở mức phát hành này không? | Lúc **chọn** mẫu | Phát hành vượt phạm vi được phép |
| Sàn số mẫu mỗi lớp | Lớp này đủ mẫu để chia tập không? | **Trước** khi đánh chỉ số lớp | Tập kiểm thử rỗng; chỉ số vô nghĩa |
| Hạn mức tổ chức | Tổ chức còn hạn mức tính toán không? | Lúc **xếp hàng** | Một tổ chức chiếm hết GPU chung |

**Ba cổng hỏi ba câu khác nhau và không thay thế được cho nhau.**

### Ràng buộc

* **BR-6.1 · BR-6.2 · BR-6.3 · BR-6.4** — xem bảng trên
* **BR-4.5** ghim phiên bản danh mục là điều kiện để tái lập
* **Giới hạn:** cách ly theo tổ chức trên nửa sau vòng đời (huấn luyện, mô hình)
  mới ở **mức kiến trúc đích**, chưa cưỡng chế ở mọi đường

---

## CN4.6 — Chạy và theo dõi huấn luyện (UC406)

### Mục đích

Cho người chạy thấy tiến độ theo chu kỳ, và thấy **bốn chỉ số** thay vì một con số
độ chính xác duy nhất.

### Giao diện 1 — Đang huấn luyện (`TrainingProgress.tsx`, 565 dòng)

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| 1 | Tiêu đề | **"Đang Huấn Luyện Mô Hình"** |
| 2 | Dòng trạng thái | **"Trạng thái:"** + trạng thái tác vụ |
| 3 | Dòng thời gian | **"Thời gian:"** + thời lượng đã chạy |
| 4 | Thanh tiến độ | **"Tiến độ huấn luyện"** + **"{n}% hoàn thành"** |
| 5 | Màn chờ | "Đang chờ epoch đầu tiên..." |
| 6 | Thẻ chỉ số | **"Mất mát khi huấn luyện"** — *Mức độ sai lệch trên tập huấn luyện* |
| 7 | Thẻ chỉ số | **"Độ chính xác trên tập huấn luyện"** |
| 8 | Thẻ chỉ số | **"Độ chính xác trên tập kiểm định"** |
| 9 | Thẻ chỉ số | **"Điểm F1"** — *Precision/Recall cân bằng* |
| 10 | Bảng lịch sử | **"Lịch Sử Metrics (5 Epoch Gần Nhất)"** — **"Mất mát:"** · **"Kiểm định:"** |
| 11 | Ghi chú | *"Mô hình sẽ được lưu tự động khi huấn luyện hoàn tất."* |

**Bốn thẻ chỉ số (6–9) đặt cạnh nhau là một quyết định về tính trung thực.** Độ
chính xác trên tập huấn luyện cao mà độ chính xác trên tập kiểm định thấp là dấu
hiệu học vẹt; hiển thị **cả hai** làm dấu hiệu đó nhìn thấy được ngay trong lúc
chạy, thay vì phải suy ra sau.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `training_jobs` | | X *(trạng thái)* | | X |
| 2 | `training_metrics` | X | | | X |
| 3 | `notifications` | X | | | X |
| 4 | Hiện vật mô hình trên đĩa | X | | | X |

### Ràng buộc

* **NFR-R7** tác vụ thất bại phải **thông báo tới chủ sở hữu tác vụ**, không chỉ
  ghi log
* Dịch vụ `trainer` tách khỏi `worker` vì **cạnh tranh tài nguyên**: một tác vụ
  huấn luyện chiếm GPU hàng giờ; chung tiến trình thì các tác vụ trích đặc trưng
  ngắn bị **bỏ đói**

---

## CN4.7 — Kết quả, lịch sử và thăng hạng (UC407)

### Mục đích

Biến một lượt chạy thành **kết quả đọc được**, so sánh được với các lượt khác, và
tách rõ *"đã huấn luyện xong"* khỏi *"đang phục vụ"*.

### Giao diện 1 — Kết quả (`ResultsInsights.tsx`, 637 dòng)

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| 1 | Tiêu đề | **"Huấn luyện hoàn tất"** |
| 2 | Tiêu đề khối | **"Chỉ số hiệu suất chính"** |
| 3 | Thẻ chỉ số | **"Độ chính xác (Accuracy)"** — *Tỷ lệ dự đoán đúng* |
| 4 | Thẻ chỉ số | **"Điểm F1"** — *Cân bằng giữa độ chuẩn xác và độ bao phủ* |
| 5 | Thẻ chỉ số | **"Số epoch đã chạy"** — *Tổng cộng {n} epoch* |
| 6 | Thẻ chỉ số | **"Điểm F1 tốt nhất"** — *Tại epoch {n}* |
| 7 | Bảng theo lớp | **"Hiệu suất theo lớp (tập test)"** |
| 8 | **Ghi chú sắp xếp** | *"Sắp xếp từ yếu nhất — các lớp F1 thấp cần thu thêm dữ liệu hoặc kiểm tra chất lượng mẫu."* |
| 9 | Cột bảng | **"Lớp"** · **"Độ chuẩn xác"** · **"Độ bao phủ"** · **"Mẫu test"** |
| 10 | Nút sao chép | Nhãn trợ năng "Sao chép {nhãn}" |
| 11 | Trạng thái rỗng | *"Chưa có dữ liệu kết quả. Bắt đầu huấn luyện để xem kết quả."* |

**Thành phần số 8 là một quyết định thiết kế đáng bảo vệ:** bảng sắp **từ lớp yếu
nhất trở đi**, không phải từ lớp mạnh nhất. Một bảng sắp từ tốt nhất sẽ để người
đọc dừng ở dòng đầu và hài lòng; sắp từ yếu nhất buộc họ nhìn vào chỗ cần làm
tiếp. Cột **"Mẫu test"** đứng cạnh để phân biệt *"lớp này thật sự kém"* với *"lớp
này chỉ có vài mẫu test nên chỉ số không có nghĩa"*.

### Giao diện 2 — Lịch sử huấn luyện (`TrainingHistory.tsx`, 243 dòng)

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| 1 | Tiêu đề khối | **"Model Tốt Nhất Theo Phương Ngữ"** |
| 2 | **Ghi chú so sánh** | *"Run tốt nhất của mỗi kiến trúc, trong cùng phương ngữ (chỉ so sánh trong cùng một hàng — khác phương ngữ là khác dữ liệu)."* |
| 3 | Biểu tượng đang phục vụ | Nhãn trợ năng **"Đã đưa vào Realtime"** / **"Đã đưa vào Realtime lúc {thời điểm}"** |
| 4 | Tiêu đề bảng | **"Lịch Sử Huấn Luyện"** + *"{n} lượt gần nhất — bấm vào một dòng để xem chi tiết"* |
| 5 | Nút | **"⟳ Làm mới"** |
| 6 | Cột bảng | **"Thời gian"** · **"Mô hình"** · **"Phương ngữ"** · **"Số vòng"** · **"Độ chính xác kiểm tra"** · **"Trạng thái"** · **"Người chạy"** · **"Xóa"** |
| 7 | Gợi ý dòng | **"Lượt {id} — {khi}. Bấm để xem chi tiết."** |
| 8 | Trạng thái rỗng | *"Chưa có phiên huấn luyện nào. Bấm "Bắt Đầu Huấn Luyện Mới" để chạy lần đầu."* |
| 9 | Màn chờ | "Đang tải lịch sử training..." |

**Ghi chú số 2 chặn một lỗi so sánh phổ biến:** hai lượt chạy trên hai phương ngữ
khác nhau chạy trên **hai tập dữ liệu khác nhau**, nên so sánh chéo hàng là so
sánh hai thứ không cùng đơn vị. Bảng vì thế nhóm theo phương ngữ và nói thẳng luật
đọc ngay dưới tiêu đề.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `training_jobs` | | X *(`promoted_at`)* | X | X |
| 2 | `training_metrics` | | | | X |
| 3 | `training_job_classes` | | | | X |
| 4 | Hiện vật mô hình | | | X | X |
| 5 | `audit_log` | X | | | |

### Ràng buộc

* **BR-6.5 — *phiên bản mới nhất* ≠ *phiên bản đang phục vụ*.** Một mô hình vừa
  huấn luyện xong **chưa phục vụ ai** cho tới khi được **thăng hạng** — một hành
  động tường minh của quản trị nền tảng, **có bản ghi**, và **đảo ngược được**.
  Biểu tượng số 3 là chỗ duy nhất trên giao diện phân biệt hai trạng thái đó
* **BR-6.6** độ tin cậy của một lượt suy luận đơn lẻ **không phải** chỉ số chất lượng

---

## CN4.8 — Thử mô hình vừa huấn luyện (UC408)

### Mục đích

Cho người chạy thử ngay mô hình mình vừa tạo, **trước khi** quyết định đề nghị
thăng hạng.

### Giao diện 1 — Thử mô hình (`TestTrainedModelModal.tsx`, 457 dòng)

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| 1 | Tiêu đề | **"Thử mô hình theo thời gian thực"** |
| 2 | Khối kết quả | **"Kết quả nhận diện"** |
| 3 | Dòng độ tin cậy | **"Độ tin cậy:"** + phần trăm |
| 4 | Nút | **"Đóng"** |

### Ràng buộc

* Thử nghiệm ở đây chạy trên **mô hình của lượt chạy đó**, không phải mô hình đang
  phục vụ — hai thứ khác nhau và không được lẫn
* **BR-6.6** con số độ tin cậy hiện ở đây là **đầu ra của một lượt chạy**, không
  phải kết quả đánh giá

---

## CN4.9 — Nhận dạng thời gian thực và đọc thành tiếng (UC409)

### Mục đích

Khép vòng đời dữ liệu: mô hình **đang phục vụ** nhận chuỗi điểm mốc từ trình duyệt
và trả nhãn kèm độ tin cậy, tuỳ chọn đọc thành tiếng.

### Điểm cuối API

Bộ định tuyến `realtime_proxy` (kết nối dài tới `realtime_service`) và `tts`.

### Giao diện 1 — Nhận diện thời gian thực (`/realtime` → `RealtimeRuntime.tsx`)

**Nhóm A — Đầu trang**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| A1 | Tiêu đề | **"Nhận diện ngôn ngữ kí hiệu"** — *"Ứng dụng nhận diện ngôn ngữ kí hiệu theo thời gian thực"* |
| A2 | Đường dẫn phân cấp | Dashboard → **"Nhận dạng realtime"** |

**Nhóm B — Cấu hình bộ nhận diện**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| B1 | Tiêu đề khối | — | **"Cấu hình nhận diện"** |
| B2 | Hộp chọn | rỗng | **"Ngôn ngữ"** — mục rỗng **"-- Chọn ngôn ngữ --"** |
| B3 | Hộp chọn | rỗng | **"Bộ nhận diện"** — mục rỗng **"-- Chọn bộ nhận diện --"** |
| B4 | Thông báo phụ thuộc | — | **"Chọn ngôn ngữ trước"** |
| B5 | Thông báo rỗng | — | **"Không có bộ nhận diện cho ngôn ngữ này"** |
| B6 | Thông báo lỗi tải | — | **"Không thể tải danh sách bộ nhận diện"** + nút **"Thử lại"** |
| B7 | Màn chờ | — | "Đang tải bộ nhận diện..." |
| B8 | Trạng thái rỗng | — | **"Không có bộ nhận diện khả dụng"** |
| B9 | Khoá khi đang chạy | — | Gợi ý: **"Không thể thay đổi khi đang xử lý"** |

**Nhóm C — Điều khiển và kết quả**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| C1 | Nút chính | **"Bắt đầu nhận diện"** / **"Dừng nhận diện"** / "Đang khởi động..." |
| C2 | Dòng trạng thái | **"Chưa bắt đầu"** / **"Đang khởi động..."** |
| C3 | Khối kết quả | **"Kết quả nhận diện"** |
| C4 | Dòng độ tin cậy | **"Độ tin cậy:"** + phần trăm |
| C5 | Dòng số mẫu | **"{n} mẫu"** |
| C6 | Trạng thái chờ | **"Chờ dữ liệu..."** / **"Chưa bắt đầu"** |

**Nhóm D — Đọc thành tiếng**

| No. | Loại điều khiển | Giá trị mặc định | Ghi chú |
|:--:|---|---|---|
| D1 | Công tắc | tắt | **"Đọc kết quả thành tiếng"**; nhãn trợ năng "Bật/Tắt đọc kết quả thành tiếng" |
| D2 | Hộp chọn | — | **"Giọng đọc"** |

**Nhóm E — Thông tin kỹ thuật**

| No. | Loại điều khiển | Ghi chú |
|:--:|---|---|
| E1 | Nút | **"Hiện thông tin kỹ thuật"** / **"Ẩn thông tin kỹ thuật"** |
| E2 | Khối | **"Thông tin kỹ thuật"** |
| E3 | Dòng | **"Trạng thái:"** |
| E4 | Dòng | **"Mã mô hình:"** (hoặc "chưa chọn") |
| E5 | Dòng | **"Thế hệ:"** — số thế hệ của phiên xử lý |
| E6 | Dòng | **"Khoá nhãn:"** |
| E7 | Dòng lỗi | **"Lỗi kỹ thuật: {chi tiết}"** |

**Nhóm B9 và "Thế hệ" (E5) cùng giải một bài toán khó của giao diện thời gian
thực:** người dùng đổi mô hình giữa chừng thì các khung hình đang bay về sẽ thuộc
mô hình cũ. Hệ thống **khoá bộ chọn khi đang xử lý** (*"Không thể thay đổi bộ nhận
diện khi đang xử lý. Vui lòng chờ đến khi xong."*) và đánh **số thế hệ** cho mỗi
phiên, để kết quả của thế hệ cũ bị loại thay vì hiển thị nhầm.

### Dữ liệu sử dụng

| No. | Bảng / cấu trúc | Thêm | Sửa | Xoá | Truy vấn |
|:--:|---|:--:|:--:|:--:|:--:|
| 1 | `recognition_profiles` | | | | X |
| 2 | `classes` | | | | X |
| 3 | Mô hình đang phục vụ (trong bộ nhớ `realtime_service`) | | | | X |
| 4 | Bitmap phút dùng thử trên Redis *(khách vãng lai)* | X | X | | X |

### Luồng ngoại lệ

| # | Tình huống | Thông báo |
|---|---|---|
| 1 | Không mở được camera | *"Chưa mở được khung hình camera. Hãy thử lại."* / *"Không khởi động được camera: {msg}"* |
| 2 | Chưa chọn mô hình | *"Chưa chọn mô hình nhận dạng."* |
| 3 | Đổi mô hình khi đang chạy | *"Không thể thay đổi bộ nhận diện khi đang xử lý. Vui lòng chờ đến khi xong."* |
| 4 | Không tải được danh sách mô hình | B6 + nút "Thử lại" |
| 5 | Không có mô hình khả dụng | B8 — trạng thái hợp lệ của một bản triển khai chưa thăng hạng mô hình nào |

### Ràng buộc

* **Phát biểu đúng mức, phải giữ nhất quán:** hệ thống **không** "nhận dạng ngôn
  ngữ ký hiệu Việt Nam". Nó phục vụ nhận dạng cho **các miền từ vựng có mô hình đã
  đăng ký** — và chính hai hộp chọn B2/B3 làm điều đó hiện ra trên giao diện
* **BR-6.5** chỉ mô hình **đã thăng hạng** mới xuất hiện trong danh sách B3
* **BR-6.6** độ tin cậy ở C4 là đầu ra của một lượt chạy, **không phải** chỉ số
  chất lượng
* Khách vãng lai đi qua `TrialGate` với hạn mức **60 phút/ngày** (CN1.9)

---

## Tổng kết ma trận chức năng ↔ use case của Nghiệp vụ 4

| Chức năng | Use case phủ | Màn hình |
|---|---|---|
| CN4.1 Xem thông tin bộ dữ liệu | UC401 | `DatasetInfo` |
| CN4.2 Chọn phương ngữ | UC402 | `DialectSelector` |
| CN4.3 Chia tập dữ liệu | UC403 | `DataSplitVisualization` |
| CN4.4 Tăng cường dữ liệu | UC404 | `AugmentationPreview` |
| CN4.5 Cấu hình và ba cổng chặn | UC405 | `TrainingSettings` |
| CN4.6 Chạy và theo dõi | UC406 | `TrainingProgress` |
| CN4.7 Kết quả, lịch sử, thăng hạng | UC407 | `ResultsInsights`, `TrainingHistory` |
| CN4.8 Thử mô hình vừa huấn luyện | UC408 | `TestTrainedModelModal` |
| CN4.9 Nhận dạng thời gian thực + TTS | UC409 | `/realtime` |
