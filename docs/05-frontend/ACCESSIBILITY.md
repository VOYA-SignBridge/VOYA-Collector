# Khả năng tiếp cận

*Lượt kiểm đầu tiên: 2026-08-10. Test ghim: `frontend/src/__tests__/accessibility.test.ts`.*

## Vì sao tài liệu này không thể vắng mặt

Đây là nền tảng thu thập và nhận dạng **ngôn ngữ ký hiệu**, tức người dùng cuối
của nó là cộng đồng khiếm thính. Một hệ thống phục vụ nhóm ấy mà chưa từng kiểm
khả năng tiếp cận là một mâu thuẫn mà người đọc kỹ sẽ nhìn ra ngay — và câu hỏi
đó đáng bị hỏi.

Tài liệu này nói ba điều, tách bạch: **đã kiểm gì**, **sửa được gì**, và — dài
nhất — **chưa kiểm gì**.

---

## 1. Đã sửa

### `<html lang="en">` trên một giao diện hoàn toàn tiếng Việt

Lỗi nặng nhất tìm được, và là lỗi một dòng.

Trình đọc màn hình chọn bộ quy tắc phát âm theo thuộc tính này. Khai `en` cho
nội dung tiếng Việt làm *"Đóng góp dữ liệu"* được đọc bằng luật tiếng Anh — ra
một chuỗi âm vô nghĩa. Trình duyệt cũng dùng nó để chọn từ điển ngắt dòng và
quyết định có gợi ý dịch trang hay không.

Vì sao nó đáng kể ở đúng dự án này: người khiếm thính bẩm sinh thường đọc chữ
viết như **ngôn ngữ thứ hai** (ngôn ngữ thứ nhất là ngôn ngữ ký hiệu, vốn có
ngữ pháp riêng), nên chất lượng văn bản và công cụ hỗ trợ đọc quan trọng hơn
mức thông thường. Và trình đọc màn hình còn là công cụ của người nhà và phiên
dịch viên đi cùng.

WCAG 3.1.1 (Level A). Đã sửa thành `lang="vi"`, có test ghim.

---

## 2. Đã kiểm và ĐẠT

| Tiêu chí | Kết quả | Bằng chứng |
|---|---|---|
| **1.1.1** Nội dung phi văn bản | đạt | mọi `<img>` đều có `alt`; ảnh trang trí dùng `alt=""` + `aria-hidden="true"` — đúng cách, không phải bỏ sót |
| **1.4.1** Không dùng riêng màu | đạt | `Badge` luôn kèm biểu tượng theo sắc thái. Đây là hệ quả của một quyết định trước đó: thương hiệu vốn đã xanh dương nên một chip xanh dương *tự nó* không nói "thành công" |
| **2.4.7** Vị trí con trỏ bàn phím | đạt | `FOCUS_RING` dùng `focus-visible`, không phải `focus` |
| **4.1.2** Tên/vai trò của thành phần | đạt một phần | 0 nút chỉ-có-biểu-tượng thiếu `aria-label` trong lượt quét |

Ghi chú về 1.4.1: quy ước "thành công = **xanh dương**" (không phải xanh lá) là
quyết định của chủ dự án và khớp bảng màu con dấu CTU. Nó buộc phải đi kèm biểu
tượng, và ràng buộc đó lại tình cờ đúng WCAG — khoảng 8% nam giới không phân
biệt được đỏ–lục.

---

## 3. CHƯA kiểm — và đây là phần dài nhất

Bốn khẳng định ở §2 kiểm được bằng cách đọc mã nguồn. Phần lớn khả năng tiếp cận
thì **không**.

| Chưa kiểm | Cần gì để kiểm |
|---|---|
| Điều hướng bằng bàn phím qua từng luồng | đi hết luồng thu mẫu, gán nhãn, quản trị chỉ bằng bàn phím |
| Trình đọc màn hình thật | NVDA / VoiceOver trên các trang chính |
| Tương phản màu | công cụ đo trên bảng màu thật, không phải đọc token |
| Thứ tự tiêu đề (`h1`→`h2`→`h3`) | quét cây tiêu đề từng trang |
| Vùng động (`aria-live`) cho toast và trạng thái tải | có thông báo nhưng chưa xác nhận trình đọc màn hình đọc được |
| Chú thích/phụ đề cho nội dung video | **chưa có** — xem dưới |
| Rung/nhấp nháy (2.3.1) | camera trực tiếp và biểu đồ thời gian thực chưa được soi |
| Thu phóng tới 200% không mất nội dung | chưa thử |

### Chỗ trống đáng nói nhất

**Nội dung video không có phụ đề hay bản chép.** Hệ thống hiển thị clip ngôn ngữ
ký hiệu, và người xem một clip ký hiệu thì đang xem *chính* nội dung — nên ở đây
"phụ đề" không phải nghĩa thông thường. Nhưng mọi hướng dẫn, thông báo và văn
bản pháp lý đi kèm thì có, và chúng chỉ tồn tại dưới dạng chữ.

Điều này **không** sửa được bằng một dòng, và không nên hứa trong quyển.

### Không có khung đa ngôn ngữ

Giao diện chỉ có tiếng Việt, không có `i18n`. Với phạm vi hiện tại (một trường
Việt Nam) đó là lựa chọn hợp lý, không phải thiếu sót — nhưng nó là ràng buộc
phải nói ra khi bàn tới việc mở rộng.

---

## 4. Điều tài liệu này KHÔNG khẳng định

Nó không nói giao diện đã tiếp cận được. Bốn test ở
`accessibility.test.ts` ghim **bốn tính chất cụ thể** đã đúng và sẽ không âm
thầm sai lại — chúng không thay được một lượt kiểm với người dùng thật.

Với một dự án phục vụ cộng đồng khiếm thính, lượt kiểm ấy nên có **người dùng
khiếm thính tham gia**, và đó là việc của con người chứ không phải của một bộ
test.

---

## 5. Nếu có thêm một ngày

Theo thứ tự lãi/công:

1. **Đi hết luồng thu mẫu bằng bàn phím.** Không cần công cụ nào, và nó là luồng
   quan trọng nhất của hệ thống.
2. **Đo tương phản** bảng màu ở `theme/status.ts` bằng một công cụ thật. Bốn sắc
   thái, mỗi cái ba biến thể — nửa giờ.
3. **Quét cây tiêu đề.** `PageHeader` dựng `h1`, các mục dùng `h2`/`h3`; xác nhận
   không trang nào nhảy cấp.
