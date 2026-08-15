# Đối chiếu danh mục nền tảng với chuẩn từ vựng quốc gia QIPEDC

*Đo ngày 14/08/2026. Sinh lại bằng `python scripts/doi_chieu_danhmuc_qipedc.py --danh-muc <danh_muc.json>`.*

Tài liệu này định lượng khoảng cách giữa **vốn từ đã có chuẩn quốc gia** và **vốn từ đã có dữ
liệu thu** — tức đúng khoảng trống mà mục 1.1 của Chương 1 phát biểu bằng lời. Dùng cho phần
đánh giá ở Chương 4 và phần hạn chế ở Chương 5.

## 1. Lấy danh mục QIPEDC mà không cần Puppeteer

Trang từ điển dùng jQuery + dataTables và phân trang **phía trình duyệt**. Toàn bộ dữ liệu về
trong một lượt gọi:

```
POST https://qipedc.moet.gov.vn/dictionary/getAll
body: group=20&text=
→ 4.362 mục, mỗi mục có _id, word, description, tl (từ loại), type, i
```

Vì vậy không cần điều khiển trình duyệt. Bản đầu của `scripts/tai_mau_qipedc.py` dò mù mã
`D0001`–`D0620` nên **bỏ sót toàn bộ 3.586 mục tiền tố `W`** — chỉ thấy 776/4.362, tức 17,8%.
Bài học: dò mã theo quy luật đoán được chỉ tìm ra thứ mình đã đoán đúng.

Tài nguyên đi kèm mỗi mục: `/videos/{id}.mp4`, `/thumbs/{id}.png`, và `/Anh/{5 ký tự đầu}.png`
(ảnh minh hoạ, chỉ với 1.682 mục có cờ `i = true`).

## 2. Cấu trúc từ điển quốc gia

**4.362 video · 3.322 mã gốc · 3.169 từ riêng biệt** (sau khi chuẩn hoá bỏ dấu và bỏ chú
thích trong ngoặc).

| Trường `type` | Số mục | Là gì |
|---|---|---|
| 0 | 4.259 | từ vựng thường |
| 2 | 63 | bảng chữ cái |
| 1 | 40 | chữ số |

Từ loại: Danh từ 2.377 · Động từ 1.062 · Tính từ 456 · Cụm từ 225 · còn lại 242.
**1.710/4.362 mục (39,2%) không có định nghĩa.**

### 2.1 Bao phủ phương ngữ rất thưa

Biến thể vùng được mã hoá bằng hậu tố `B`/`N`/`T` trên mã video.

| Mô hình biến thể | Số từ gốc | Tỉ lệ |
|---|---|---|
| **Không có biến thể vùng nào** | 2.742 | **82,5%** |
| Đủ cả Bắc – Nam – Trung | 483 | 14,5% |
| Có một phần (thiếu 1–2 vùng) | 97 | 2,9% |

Khi có biến thể thì phân bố rất cân: Bắc 534 · Nam 547 · Trung 522.

Phải phát biểu chính xác: 82,5% "không ghi vùng" **không** có nghĩa từ đó không có biến thể
vùng trong thực tế ngôn ngữ — nghĩa là **từ điển chưa thu biến thể cho nó**. Đây là khoảng
trống *bao phủ*, không phải một khẳng định ngôn ngữ học.

## 3. Đối chiếu với danh mục nền tảng

Ghép theo văn bản đã chuẩn hoá, không ghép theo mã — hai hệ mã hoàn toàn độc lập.

| | |
|---|---|
| Lớp ký hiệu của nền tảng | **63** |
| Có mặt trong từ điển quốc gia | **40 (63,5%)** |
| Không khớp | 23 |

23 lớp không khớp gồm: `spa` 9 · `hoa-de` 8 · `can-tho` 3 · `common` 3 — tức phần vốn từ theo
chiến dịch riêng, không thuộc vốn từ phổ thông của từ điển. Điều này **đúng như thiết kế**: hệ
thống phải chứa được vốn từ ngoài chuẩn quốc gia, và đó chính là lý do Chương 2 tách *danh mục
hệ thống* khỏi *dữ liệu theo tenant*.

## 4. Phát hiện chính: biến thể vùng bị gộp ở 26,8% kho mẫu

Trong 40 lớp khớp, **15 lớp có đủ ba biến thể vùng trong từ điển quốc gia**. Nhưng nền tảng
chỉ gán nhãn vùng cho **3 lớp** (`bac` 1, `nam` 1, `trung` 1).

Chênh lệch nằm ở **12 chữ cái**: từ điển quốc gia ghi nhận ba dạng ký hiệu riêng cho mỗi chữ,
còn nền tảng gộp thành một lớp `bang-chu-cai` **không ghi vùng**:

| Chữ | Số mẫu đã thu | | Chữ | Số mẫu đã thu |
|---|---|---|---|---|
| A | 206 | | Â | 70 |
| T | 95 | | Ê | 70 |
| E | 85 | | Ô | 70 |
| O | 83 | | P | 70 |
| H | 75 | | Ơ | 60 |
| X | 75 | | | |
| Ă | 75 | | **Tổng** | **1.034** |

**1.034 / 3.860 mẫu = 26,8% toàn bộ kho** nằm ở những lớp mà biến thể vùng tồn tại trong chuẩn
quốc gia nhưng không được ghi lại lúc thu. Toàn bộ nhóm bảng chữ cái là 2.487 mẫu (64,4% kho).

### Vì sao đây là phát hiện chứ không phải lỗi

Mục 1.1 của Chương 1 lập luận rằng khác biệt vùng miền phải được ghi nhận như **một thuộc tính
của dữ liệu** thay vì bị xem mặc nhiên là nhiễu cần loại bỏ. Đây là một **ca cụ thể, đo được,
xảy ra ngay trên dữ liệu của chính đề tài**: thuộc tính đó không được ghi tại thời điểm thu,
và mục 1.2.3 đã nói trước rằng những gì không ghi lúc đó **không tái tạo đáng tin cậy về sau**
— muốn biết 206 mẫu chữ "A" thuộc dạng vùng nào thì phải hỏi lại từng người ký, hoặc thu lại.

Đây chính là lý do đề tài thiết kế trường phương ngữ ở tầng danh mục thay vì để tên thư mục
mang nghĩa. Cơ chế đã có; dữ liệu cũ thu trước khi cơ chế có mới là phần chưa vá.

**Cách viết vào quyển:** nêu như một hạn chế đã định lượng của tập dữ liệu hiện tại, kèm ghi
chú rằng lược đồ hiện hành đã có chỗ để ghi thuộc tính này. Đừng viết thành "từ điển quốc gia
đầy đủ hơn hệ thống" — hai thứ khác mục đích: một bên là từ điển tra cứu, một bên là kho mẫu
huấn luyện nhiều mẫu trên mỗi lớp.

## 5. Việc kéo theo

1. **Không backfill bằng suy đoán.** Không được gán vùng cho 1.034 mẫu cũ dựa trên nơi thu
   hoặc trên người ký — đó là bịa siêu dữ liệu, đúng loại lỗi mà
   `docs/10-issues/HARDCODED_VOCABULARY_AUDIT.md` đã kiểm kê. Để trống và ghi rõ là không
   biết.
2. **Chiến dịch thu sau phải chọn vùng tường minh** cho lớp bảng chữ cái, ít nhất với 12 chữ
   nêu trên.
3. **Cân nhắc dùng danh mục QIPEDC làm nguồn cho danh mục hệ thống** — 3.169 từ có sẵn từ
   loại và định nghĩa. Nhưng nhớ kết quả ở `DO_HIEU_QUA_LUU_TRU.md` §4.3: video từ điển có
   trung vị 35% thời lượng là người ký đứng nghỉ, nên **không dùng thẳng làm mẫu huấn luyện**
   được; giá trị của nó nằm ở *danh mục*, không ở *video*.
