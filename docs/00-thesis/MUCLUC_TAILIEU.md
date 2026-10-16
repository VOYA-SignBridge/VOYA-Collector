# Mục lục tài liệu luận văn

*Bản đồ các tài liệu trong thư mục này: mỗi tài liệu phục vụ chương nào, chứa
loại nội dung gì, và nên trích dẫn ra sao.*

---

## 1. Ba loại tài liệu, đừng lẫn

Các tài liệu ở đây thuộc ba loại có mức độ ràng buộc khác nhau. Việc trích nhầm
loại là nguyên nhân phổ biến nhất khiến một câu trong quyển bị phản biện bác bỏ.

| Loại | Nội dung | Cách trích dẫn |
|---|---|---|
| **Thuyết minh** | Kiến trúc, nghiệp vụ, lập luận thiết kế, nguyên lý | Đưa thẳng vào Chương 3 dưới dạng văn xuôi |
| **Phép đo** | Số liệu thực nghiệm, có giao thức và điều kiện | Đưa vào Chương 4, **bắt buộc kèm giới hạn** |
| **Rà soát** | Đối chiếu cam kết với hiện trạng mã nguồn | Dùng để xác định mức phát biểu, không dùng làm số liệu |

Nguyên tắc chung: **một tài liệu rà soát không sinh ra được một con số cho Chương
4**, và **một phép đo không thay thế được lập luận thiết kế ở Chương 3**.

---

## 2. Bốn bản thuyết minh — nền cho Chương 3

Bốn tài liệu này viết theo văn phong luận văn, không chứa định danh kỹ thuật, và
có thể dùng gần như nguyên văn.

### `THUYETMINH_KIENTRUC_VA_NGHIEPVU.md`

Kiến trúc tổng thể và vòng đời dữ liệu. Trả lời: vì sao là nền tảng chứ không phải
một bộ dữ liệu; ba miền dữ liệu và ranh giới giữa chúng; hành trình một mẫu từ lúc
thu tới lúc góp phần vào mô hình; vấn đề hai mặt phẳng lưu trữ; các nguyên lý
thiết kế; so sánh các phương án đã cân nhắc.

Chứa bảng so sánh cho bốn quyết định lớn: cách ly dữ liệu, biểu diễn dữ liệu, tổ
chức các bước xử lý, và thẩm quyền ký số.

### `THUYETMINH_NGHIEPVU_VANHANH.md`

Nghiệp vụ ở góc nhìn người dùng. Trả lời: ai tham gia và với quyền gì; vòng đời tổ
chức và tài khoản; kiểm soát truy cập; đồng thuận và khuôn khổ pháp lý; quản trị
dữ liệu thường ngày; nhật ký kiểm toán.

### `THUYETMINH_PHUONGPHAP_DANHGIA.md`

Phần mở đầu Chương 4. Trả lời: đánh giá cái gì và vì sao không đánh giá độ chính
xác mô hình; bốn trục đánh giá; nguyên lý phép đo phải có khả năng thất bại; điều
kiện đo và tính hợp lệ; quy tắc phát biểu kết quả.

### `THUYETMINH_VANHANH_VA_DOTINCAY.md`

Triển khai, sao lưu, giám sát, hạ tầng kiểm thử, và các bài học sự cố. Phần này
thường bị bỏ qua nhưng nó chứng minh hệ thống thực sự vận hành được, không chỉ
chạy được trên máy phát triển.

---

## 3. Các phép đo — số liệu cho Chương 4

Mỗi phép đo có một tài liệu thuyết minh và một tệp dữ liệu thô đi kèm.

### `MEASUREMENT_storage_efficiency.*` — hiệu quả lưu trữ

```
Kết quả công bố:  giảm 92,2% tổng dung lượng
                  trung vị mỗi mẫu 91,6%, khoảng p5–p95: 88,9–94,7%
Cỡ mẫu:           54 cặp khớp thời lượng, đạt ngưỡng phát hiện
Trạng thái:       ĐÓNG
```

Giới hạn bắt buộc nêu kèm: nguồn video là bản quay đã nén để phân phối trên web,
không phải luồng thu của chính hệ thống. **Không** phát biểu con số này như đo trên
dữ liệu do nền tảng thu.

Tài liệu ghi rõ hai con số cao hơn (97,6% và 95,5%) đã bị loại và vì sao — một cái
hưởng lợi từ việc cắt bớt thời lượng, một cái hưởng lợi từ những mẫu mà quá trình
trích xuất thất bại. Phần phân tích tính hợp lệ này đáng giữ, vì nó chứng minh vì
sao 92,2% là ước lượng được chọn.

### `MEASUREMENT_api_latency.*` — độ trễ dịch vụ

```
Trạng thái:  ĐÓNG
```

Đo trong môi trường có kiểm soát. **Không** phát biểu như một chứng minh về cô lập
hiệu năng giữa các đơn vị. Không có hệ số quy đổi nào giữa các cấu hình khác nhau.

### `MEASUREMENT_sot_integrity.*` — toàn vẹn nguồn sự thật

```
Kịch bản thực thi:  9/9, đều cho kết quả xác định
Thoả thuộc tính:    8
Phát hiện giới hạn: 1 (thứ tự phiên bản)
Trạng thái:         ĐÓNG
```

**Không** báo cáo là "9/9 đạt". Phép đo hợp lệ ở cả chín ca; thuộc tính bảo mật đạt
ở tám. Ca thứ chín phát hiện rằng một con trỏ phiên bản ký hợp lệ vẫn trỏ về bản
cũ được — tài nguyên không bị xoá, nhưng giá trị dùng chung bị ghi đè lùi.

Ba thuộc tính phải tách khi phát biểu: toàn vẹn (đạt), xác thực nguồn (đạt), đơn
điệu phiên bản (chưa cưỡng chế).

### `MEASUREMENT_tenant_isolation.*` — cách ly dữ liệu

```
Trạng thái:  CHƯA ĐÓNG
```

Tài liệu hiện mang cảnh báo không trích dẫn số liệu. Lượt đo trước bị loại vì đối
chứng dương không đạt: tài khoản chủ sở hữu cũng không đọc được dữ liệu của chính
mình, nên mọi kết quả "đã bị chặn" không phân định được nguyên nhân.

Điều kiện và trình tự chạy lại: xem phần tương ứng trong
`PROPOSAL_COMMITMENT_TRACEABILITY.md`.

---

## 4. Rà soát hiện trạng — xác định mức phát biểu

### `AUDIT_async_pipeline.md`

Bốn năng lực xử lý bất đồng bộ đều vận hành trên tiến trình nền. Hai trục ngang
yếu: cơ chế thử lại không đồng đều, và tính bất biến khi lặp chưa bảo đảm cho việc
tạo tài nguyên và tải đối tượng.

Kết luận cho cam kết tương ứng: **đạt, có hạn chế về độ tin cậy** — không phải "đạt
một phần" về năng lực.

### `AUDIT_realtime_recognition.md`

Đường nhận dạng nối đủ chặng và đã chạy được một lượt suy diễn đúng nhãn trên mẫu
thật của kho. Trạng thái: vận hành được, có điều kiện tiên quyết.

**Không** phát biểu là "hệ thống nhận dạng ngôn ngữ ký hiệu tiếng Việt" — nó phục
vụ hai miền từ vựng có mô hình đã đăng ký. **Không** trích độ tin cậy của một lượt
suy diễn như một chỉ số chất lượng.

### `MODEL_tenant_ml_domain.md`

Đối chiếu kiến trúc đích với hiện thực, dùng ba mức ký hiệu để phân biệt *đã cưỡng
chế*, *đã hiện thực nhưng khác phạm vi đích*, và *mới là kiến trúc đích*.

Đây là tài liệu quan trọng nhất để tránh một lỗi phát biểu cụ thể: mô tả hệ thống
như cô lập toàn bộ vòng đời từ thu nhận tới mô hình, trong khi nửa sau chưa được
cưỡng chế theo ranh giới đơn vị.

---

## 5. Truy vết cam kết

### `PROPOSAL_COMMITMENT_TRACEABILITY.md`

Tài liệu trung tâm. Bảng đối chiếu tám mục tiêu của đề cương với trạng thái cuối,
bằng chứng chính, và giới hạn.

Ngoài bảng, tài liệu chứa:

- Lập luận cho các tinh chỉnh so với đề cương (phân tầng phạm vi, lựa chọn thư
  viện trích xuất đặc trưng).
- Ba phát biểu phải hạ mức, kèm câu thay thế cụ thể — dùng đồng bộ ở phần Tóm tắt
  và phần Kết luận.
- Trình tự và điều kiện để đóng phép đo cách ly.
- Ranh giới phạm vi của phép đo ấy.

---

## 6. Ba phát biểu phải hạ mức — tóm tắt

Đây là nội dung dễ bị bỏ sót nhất khi viết Tóm tắt và Kết luận, vì bản nháp thường
được viết trước khi có kết quả đo.

| | Không viết | Viết |
|---|---|---|
| Phân quyền | triển khai đầy đủ ở bốn cấp phạm vi | kiến trúc hỗ trợ nhiều cấp; cưỡng chế hiện ở cấp hệ thống và cấp đơn vị |
| Bất đồng bộ | bảo đảm thử lại an toàn và bất biến khi lặp | thực hiện bất đồng bộ bốn năng lực; thử lại và tính bất biến chưa đồng đều |
| Nguồn sự thật | bảo đảm trạng thái mới nhất luôn thắng | cung cấp bằng chứng giả mạo và xác thực nguồn; chưa cưỡng chế thứ tự phiên bản |

---

## 7. Thứ tự đọc đề nghị

Với người đọc muốn nắm nhanh:

```
1. THUYETMINH_KIENTRUC_VA_NGHIEPVU     — hệ thống là gì, vì sao thiết kế vậy
2. MODEL_tenant_ml_domain              — đích và hiện thực cách nhau ở đâu
3. THUYETMINH_PHUONGPHAP_DANHGIA       — đánh giá theo cách nào và vì sao
4. PROPOSAL_COMMITMENT_TRACEABILITY    — đã hoàn thành tới đâu
```

Với người viết Chương 3: hai bản thuyết minh đầu, cộng phần so sánh phương án.

Với người viết Chương 4: bản thuyết minh phương pháp, các tài liệu phép đo, và
bảng truy vết.
