# Đo hiệu quả lưu trữ của biểu diễn theo điểm mốc

*Đo ngày 14/08/2026 trên máy phát triển. Sinh lại bằng
`python scripts/do_hieu_qua_luu_tru.py`.*

Tài liệu này là **bằng chứng cho MT6** (mục 1.3 của Chương 1) và là nguồn số liệu cho phần
đánh giá ở Chương 4. Nó thay thế mọi con số lưu trữ xuất hiện trong các bản nháp cũ —
**"90%" và "99,1%" không có nguồn gốc đo đạc và không được dùng lại.**

## 1. Cách đo

Đối tượng đo là hai kho tệp `.npz` trên đĩa: `dataset/features/` (chuỗi đã chuẩn hoá, đầu
vào mô hình) và `dataset/raw/` (chuỗi trước chuẩn hoá, kho bản ghi nguồn).

Số khung của mỗi mẫu đọc từ tiêu đề `.npy` bên trong `.npz` bằng `zipfile`, **không qua
numpy** — bản numpy trong `.venv_py313_backup` trên máy này báo *"built with MINGW-W64 …
CRASHES ARE TO BE EXPECTED"* và segfault khi nạp. Đọc tiêu đề trực tiếp vừa tránh được lỗi
đó, vừa cho phép lấy `compress_size` của **từng mảng**, thứ numpy không lộ ra.

Nhịp thu quy ước là **30 fps**, dùng để quy đổi byte/khung sang byte/giây.

## 2. Kết quả đo

### 2.1 Kho đã chuẩn hoá — `dataset/features/`

| Chỉ số | Giá trị |
|---|---|
| Số mẫu | 3.871 |
| Tổng dung lượng | 146,0 MB |
| Trung vị mỗi tệp | 42,6 KB |
| Khoảng nhỏ nhất – lớn nhất | 13,9 – 84,0 KB |
| Trung vị số khung | 60 (≈ 2,00 giây ở 30 fps) |
| Chi phí trung bình mỗi khung | **659,2 byte** |
| Chi phí trung bình mỗi giây thu | **19,31 KB/s** |
| Tỉ lệ nén của `.npz` | 1,69× |

### 2.2 Kho trước chuẩn hoá — `dataset/raw/`

| Chỉ số | Giá trị |
|---|---|
| Số mẫu | 440 |
| Tổng dung lượng | 10,2 MB |
| Trung vị mỗi tệp | 27,5 KB |
| Chi phí trung bình mỗi khung | 407,0 byte |
| Chi phí trung bình mỗi giây thu | 11,92 KB/s |
| Tỉ lệ nén của `.npz` | 1,27× |

### 2.3 Ba bố cục tệp cùng tồn tại trong `features/`

Con số 659,2 byte/khung ở §2.1 là **trung bình của ba bố cục khác nhau**, không phải chi phí
của biểu diễn. Tách ra:

| Bố cục | Số tệp | Tỉ lệ | Byte/khung |
|---|---|---|---|
| `sequence` + `meta` | 1.434 | 37,0% | **298,4** |
| `sequence` + `landmarks_normalized` + `meta` | 440 | 11,4% | 804,6 |
| `sequence` + `landmarks_normalized` + `landmarks_raw` + 3 mặt nạ + `meta` | 1.997 | 51,6% | 886,3 |

**Chi phí thật của biểu diễn theo điểm mốc là 298,4 byte/khung**, tức **8,74 KB mỗi giây
thu** — đọc từ bố cục tối thiểu. Đây là con số nên dùng khi nói "biểu diễn theo điểm mốc tốn
bao nhiêu".

Đối chiếu lý thuyết: một khung là 21 điểm × 3 toạ độ × 2 bàn tay × 4 byte (`float32`) =
**504 byte**. Trên đĩa còn 298,4 byte, tức `.npz` nén được xuống **0,59×**.

## 3. Phát hiện: 28,9% kho là bản sao thừa

Bóc dung lượng nén theo từng mảng trên toàn bộ 3.871 tệp:

| Mảng | Dung lượng | Tỉ lệ kho |
|---|---|---|
| `sequence` | 65,7 MB | 45,0% |
| `landmarks_normalized` | 42,2 MB | **28,9%** |
| `landmarks_raw` | 32,2 MB | 22,0% |
| `meta` | 3,2 MB | 2,2% |
| 3 mặt nạ hợp lệ | 0,3 MB | 0,2% |

So mã kiểm dư vòng (CRC-32) của từng mảng trong từng tệp cho thấy: ở **cả 2.437 tệp** có
`landmarks_normalized`, mảng này **trùng byte-for-byte với `sequence`**. Không tệp nào lệch.

Ngược lại, `landmarks_raw` **không** trùng `sequence` ở bất kỳ tệp nào — đúng như thiết kế,
vì đó là chuỗi trước chuẩn hoá và nó phục vụ khả năng tái xử lý (mục 1.5.2 của Chương 1).

Nghĩa là **42,2 MB trong 146,0 MB — 28,9% kho — là một bản sao thừa dưới tên khác.** Xoá
`landmarks_normalized` khỏi các tệp đó không mất thông tin nào.

Đây là một phát hiện của phép đo, không phải một suy đoán, và nó có hai hệ quả:

1. **Với luận văn:** con số 19,31 KB/s ở §2.1 phản ánh *kho hiện tại*, còn 8,74 KB/s phản
   ánh *biểu diễn*. Chương 4 phải nói rõ đang báo cáo cái nào. Trộn hai con số này là chỗ
   phản biện bắt được.
2. **Với hệ thống:** cần tìm chỗ ghi cả hai tên rồi bỏ một. Việc này **chưa làm** — sửa đường
   ghi mà không di trú 2.437 tệp cũ sẽ tạo bố cục thứ tư.

## 4. So sánh với video — đo ghép cặp trên 40 mẫu QIPEDC

`dataset/raw_videos/` trên máy phát triển rỗng, nên phép so không thể thực hiện trên dữ liệu
của chính hệ thống. Thay vào đó, phép đo dùng **40 video công khai của từ điển QIPEDC**
\cite{bogddt_qipedc_2019}, chạy **đúng cấu hình MediaPipe mà nền tảng dùng khi thu**
(`maxNumHands 2`, `modelComplexity 1`, ngưỡng 0,70/0,75 — hồ sơ `capture` trong
`frontend/src/config/handTracking.ts`), rồi so từng cặp *video ↔ chuỗi điểm mốc trích từ
chính video đó*.

Sinh lại bằng `.venv/Scripts/python.exe scripts/do_video_vs_diemmoc.py --tai 40`.
Mã được rải đều trên dải D0001–D0620 thay vì lấy 40 mã đầu, vì các mã liền nhau nhiều khả
năng cùng một buổi quay.

### 4.1 Mẫu video

Trung vị **4,22 giây**, **30 fps**, **1280×720** ở cả 40/40 mẫu, trung vị **641,6 KB** mỗi
tệp — tức bitrate thực đo **1,22 Mbps**.

| Đại lượng | Video | Điểm mốc (đủ khung) | Điểm mốc (60 khung, như nền tảng lưu) |
|---|---|---|---|
| Trung vị mỗi mẫu | 641,6 KB | 35,4 KB | 21,3 KB |
| Trên mỗi giây thu | 152,0 KB/s | 8,38 KB/s | — (cố định theo mẫu) |
| Bitrate tương đương | 1,22 Mbps | 0,067 Mbps | — |

**Kiểm chéo:** 8,38 KB/s đo ở đây, so với **8,74 KB/s** đo độc lập trên kho thật của hệ thống
ở §2.3. Hai phép đo trên hai tập dữ liệu khác nhau, bằng hai đường khác nhau, lệch **4%**.
Đây là bằng chứng cho thấy con số chi phí biểu diễn là ổn định.

### 4.2 Phải lọc theo tỉ lệ phát hiện, nếu không số sẽ bị thổi phồng

Khoảng dao động thô rất rộng — 14×–126× — và nguyên nhân không phải nén.

Khung nào MediaPipe không bắt được bàn tay nào thì vector 126 chiều **toàn số 0**, và
`savez_compressed` nén nó gần như miễn phí. Một tệp `.npz` nhỏ bất thường vì thế **không**
phản ánh biểu diễn hiệu quả — nó phản ánh **hỏng phát hiện**. Gộp chung là tự thổi phồng kết
quả của chính mình.

Tách theo tỉ lệ khung bắt được tay:

| Nhóm | n | Tỉ lệ (60 khung) | Tỉ lệ (đủ khung) |
|---|---|---|---|
| Toàn mẫu | 40 | 45,3× (14,1–126,3) | 17,2× (9,3–57,8) |
| **Bắt được tay ≥ 90%** | **19** | **24,7× (14,1–86,6)** | **12,0× (9,3–17,4)** |
| Bắt được tay < 90% | 21 | 63,1× (22,9–126,3) | 27,9× (13,1–57,8) |

**Con số dùng được: ≈ 25×, tiết kiệm 96,0%** — trung vị của nhóm phát hiện tốt. Con số thô
45× cao hơn gần gấp đôi và không được dùng.

### 4.3 Tỉ lệ phát hiện thấp KHÔNG phải hỏng phát hiện

Lượt đo đầu cho tỉ lệ bắt được bàn tay trung vị **81%** trên toàn video, và điều đó **đã bị
tôi hiểu sai thành hỏng phát hiện**. Ghi lại cả quá trình vì kết luận sai suýt vào luận văn.

**Bước 1 — thử chỉnh cấu hình.** Chạy năm cấu hình trên 12 mẫu (9 kém nhất + 3 tốt nhất),
`scripts/thu_cau_hinh_nhandang.py`:

| Cấu hình | Trung vị |
|---|---|
| A — hồ sơ `capture` của nền tảng (0,70/0,75, toàn khung) | 45,2% |
| B — toàn khung, ngưỡng 0,50/0,50 | **49,3%** |
| C — cắt khung theo vùng chuyển động, ngưỡng 0,70 | 45,4% |
| D — cắt khung, ngưỡng 0,50 | 48,8% |
| E — cắt khung + dò lại mọi khung (`static_image_mode`) | 48,6% |

Hạ ngưỡng, cắt khung để bàn tay to lên, bỏ chế độ bám để dò lại từng khung — tất cả chỉ nhích
được **4 điểm phần trăm**. Kết quả lại **nhị phân**: mẫu nào cũng hoặc ~40–50%, hoặc đúng
100%, không có ở giữa. Đó không phải dáng điệu của một vấn đề về ngưỡng hay tỉ lệ.

**Bước 2 — nhìn khung hình.** Vẽ chuỗi khung có/không phát hiện cho một mẫu kém:

```
D0031B  138 khung
########...............................................####.###########...........
```

Các khoảng trống nằm liền khối ở **đầu và cuối**, không rải rác. Trích đúng những khung đó ra
xem thì rõ: người ký **đứng nghỉ, hai tay buông xuôi ra ngoài khung hình**. Không có bàn tay
nào để bắt. MediaPipe không hỏng.

**Bước 3 — đo lại cho đúng đại lượng.** `scripts/do_doan_ky_hieu.py` tách đoạn có ký hiệu
(cho phép hụt tối đa 6 khung liên tiếp) rồi đo riêng trong đoạn đó. Trên **150 video**:

| Đại lượng | Trung vị | Tứ phân vị |
|---|---|---|
| Dẫn vào — đứng nghỉ đầu video | 11,5 khung ≈ 0,38 giây | |
| Dẫn ra — đứng nghỉ cuối video | 25,0 khung ≈ 0,83 giây | |
| Phần thời lượng thực sự có ký hiệu | **64,7%** | 52,3 – 100% |
| Phát hiện tính trên **toàn video** | 68,5% | |
| **Phát hiện tính trong đoạn ký** | **98,3%** ← số đúng | 95,8 – 100% |

Gộp toàn bộ: **14.301 / 19.884 khung có ký hiệu = 71,9%**; phần còn lại là đứng nghỉ.
**138/150 mẫu (92,0%)** đạt từ 90% phát hiện trở lên trong đoạn ký. Thấp nhất là 82,8% — không
mẫu nào thực sự hỏng phát hiện.

Phân bố lệch chứ không đều: **52/150 video (34,7%) không có đoạn nghỉ nào**, cắt luôn vào ký
hiệu; số còn lại có phần đệm dài ngắn khác nhau, cá biệt có mẫu chỉ 1,1% thời lượng là ký
hiệu. Nghĩa là **không thể cắt bằng một quy tắc thời gian cố định** — phải dò theo nội dung.

**Đối chiếu quyết định:** chính nền tảng, thu bằng webcam ở cự ly gần, đạt **100% khung có ít
nhất một bàn tay trên cả 1.997 mẫu** có mặt nạ hợp lệ (`frame_valid_mask`). Đường thu của hệ
thống không có vấn đề gì cả.

**Ý nghĩa cho đề tài.** Đây là bằng chứng đo được cho khẳng định ở mục 1.1 và 1.2.5 của
Chương 1 — QIPEDC là *nguồn tham chiếu vốn từ*, không phải *bộ dữ liệu huấn luyện sẵn dùng*:
muốn dùng video từ điển làm dữ liệu thì phải **cắt đoạn trước**, và bước cắt đoạn đó chính là
loại siêu dữ liệu mà mục 1.2.3 nói rằng phải ghi nhận tại thời điểm thu chứ không dựng lại
được về sau. Phát biểu phải đúng như vậy — không phải "từ điển quốc gia nhận dạng kém".

### 4.4 Giới hạn của phép so này

Video QIPEDC là **bản quay studio, đã hậu kỳ và nén để phát web** ở 1280×720. Đó **không** là
luồng webcam mà CTU-SignBridge thu. Vì vậy tỉ lệ 25× đặc trưng cho *"video như QIPEDC phân
phối"*, không phải *"video như nền tảng thu"*. Câu trong luận văn phải nói rõ điều này.

Đây vẫn hơn hẳn một bitrate giả định: mốc so sánh **có tên, công khai, và tái lập được** —
người phản biện tải đúng 40 tệp đó và chạy lại được.

Muốn có số trên dữ liệu của chính hệ thống: thu 5–10 mẫu có giữ video gốc qua giao diện, rồi
chạy `scripts/do_hieu_qua_luu_tru.py` — script tự phát hiện video trong `dataset/raw_videos/`.

### 4.5 Ghi chú kỹ thuật khi tải lại

Chứng chỉ TLS của `qipedc.moet.gov.vn` (Let's Encrypt) **hết hạn ngày 16/07/2026**, nên thư
viện HTTP thông thường từ chối kết nối. Script không tắt xác minh một cách mù quáng: nó lấy
chứng chỉ một lần, **ghim vân tay SHA-256**, rồi kiểm lại ở mọi kết nối — bỏ qua đúng phần
*hạn dùng*, giữ nguyên phần *danh tính*, và dừng hẳn nếu vân tay đổi giữa chừng. Chỉ tải nội
dung công khai, không gửi thông tin xác thực nào.

## 5. Câu dùng được trong Chương 4

> Biểu diễn theo điểm mốc chiếm **298,4 byte cho mỗi khung hình**, tương đương **8,74 KB cho
> mỗi giây thu** ở nhịp 30 fps, đo trên 3.871 mẫu của nền tảng. Con số này thấp hơn kích
> thước lý thuyết của mảng chưa nén (504 byte/khung) nhờ phép nén của định dạng `.npz`, đạt
> tỉ lệ 0,59×. Một phép đo độc lập trên 40 video từ điển QIPEDC cho 8,38 KB/s, lệch 4% so với
> con số trên.
>
> So sánh ghép cặp trên 40 video đó — mỗi video được trích điểm mốc bằng đúng cấu hình
> MediaPipe mà nền tảng dùng khi thu — cho tỉ lệ **khoảng 25 lần**, tương đương **tiết kiệm
> 96,0%** dung lượng, tính trên nhóm 19 mẫu có tỉ lệ phát hiện bàn tay từ 90% trở lên. Nếu
> không lọc theo tỉ lệ phát hiện, tỉ lệ thô là 45 lần; chênh lệch này đến từ việc các khung
> không phát hiện được bàn tay được lưu thành vector không và bị nén gần như miễn phí, nên
> không phản ánh hiệu quả của biểu diễn. Cần lưu ý video QIPEDC là bản quay studio ở độ phân
> giải 1280×720 với bitrate đo được 1,22 Mbps, không phải luồng webcam mà hệ thống thu; tỉ lệ
> nêu trên vì vậy đặc trưng cho phép so với loại video này.
>
> Kho lưu trữ thực tế hiện chiếm 146,0 MB, cao hơn mức tối thiểu vì 28,9% dung lượng là một
> bản sao trùng lặp của chuỗi đã chuẩn hoá được ghi dưới hai tên khác nhau — một khiếm khuyết
> hiện thực được phát hiện trong quá trình đo, chưa khắc phục tại thời điểm viết.
