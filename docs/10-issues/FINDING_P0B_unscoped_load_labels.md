# Phát hiện trong lúc đo P0-B: bảy đường gọi chưa chuyển phạm vi

**Trạng thái:** ĐÃ ĐÓNG 16/08/2026 tại `47a8846` — xem "Kết cục" ở cuối
**Số nơi gọi thật:** **11**, không phải 7 — xem "Đính chính con số"
**Phát hiện lúc:** 16/08/2026, trong lượt đo cách ly xuyên kho (P0-B)
**Thuộc bản mã:** `19a8f75`, ảnh chụp mã `1961904ccb07ab25`
**Mức độ:** một lỗi CHẶN ĐƯỜNG CHÍNH, một lỗi làm hỏng đồng bộ khởi động

---

## Vì sao ghi lại thay vì sửa ngay

Quy tắc đã chốt cho vòng đo này: **không sửa trong lúc đo.** Nếu lượt đo làm lộ
một lỗi mới, lỗi ấy được ghi thành phát hiện *của chính bản mã đang đo*, chứ
không được vá rồi đo tiếp.

Lý do không phải là hình thức. Sửa giữa chừng thì con số thu được sau đó thuộc
về một bản mã khác bản mã đã đóng băng, và toàn bộ chuỗi truy nguyên — ảnh chụp
mã, băm cây, đối chiếu từng mô-đun trong container — mất ý nghĩa. Một kết quả
không quy thuộc được cho phiên bản nào thì không bảo vệ được điều gì.

Vì vậy tài liệu này là *kết quả* của phép đo, ngang hàng với các con số, không
phải một việc tồn đọng bên lề.

---

## Điều đã quan sát được

Hàm đọc danh mục lớp từ kho tệp gần đây được siết lại: nó **bắt buộc** phải nhận
phạm vi đơn vị, và ném lỗi khi không có, thay vì lặng lẽ trả về toàn bộ kho. Đây
là một thay đổi đúng — nó biến một đường rò im lặng thành một lỗi ồn ào.

Nhưng lượt chuyển đổi các nơi gọi chưa hoàn tất. Bảy nơi vẫn gọi hàm ấy mà không
truyền phạm vi. Hai trong số đó nằm trên đường đi thật và đã được quan sát trực
tiếp trong lúc đo:

### 1. Tạo lớp mới trả về lỗi máy chủ

Đường tạo lớp — thao tác cốt lõi nhất của sản phẩm — kết thúc bằng một bước dựng
lại chỉ mục nhãn, và bước ấy đọc danh mục **không kèm phạm vi**. Kết quả: mọi
yêu cầu tạo lớp từ một tài khoản đơn vị thường đều trả về lỗi máy chủ.

Quan sát trực tiếp: hai lượt gọi liên tiếp với hai nội dung hợp lệ khác nhau,
cả hai đều trả về lỗi máy chủ, và vết ngăn xếp dừng đúng tại lời gọi thiếu phạm
vi.

Điều đáng chú ý về mặt phương pháp: cổng quyền đã cho qua. Tài khoản có đúng vai
biên tập của đơn vị, dữ liệu gửi lên hợp lệ. Lỗi nằm sau cổng quyền, ở tầng dữ
liệu — nên không một phép kiểm phân quyền nào bắt được nó.

### 2. Đồng bộ dữ liệu lúc khởi động thất bại

Khi tiến trình phục vụ khởi động, nó chạy một lượt đồng bộ từ kho tệp sang cơ sở
dữ liệu để bù các hàng còn thiếu. Lượt ấy cũng đọc danh mục không kèm phạm vi và
ném đúng lỗi trên.

Hệ thống xử lý tình huống này **đúng cách**: nó bắt lỗi, ghi nhật ký rõ ràng
rằng lược đồ vẫn nguyên vẹn và cơ sở dữ liệu không bị đụng tới, rồi khởi động
tiếp. Không có hỏng hóc âm thầm. Nhưng hệ quả vẫn là: cơ chế bù hàng thiếu hiện
không hoạt động, và không ai được báo ngoài một dòng nhật ký mức lỗi.

### 3. Năm nơi còn lại

Năm nơi khác cũng gọi thiếu phạm vi: bộ cân bằng dữ liệu, bộ phân loại lại
phương ngữ, đường xuất dữ liệu, bộ đề bạt danh mục dùng chung, và một nhánh nội
bộ trong chính mô-đun quản lý dữ liệu. Chưa nơi nào trong số này được quan sát
trực tiếp trong lượt đo, nên không khẳng định chúng hỏng — chỉ khẳng định chúng
mang **cùng một hình dạng** với hai nơi đã hỏng thật.

---

## Vì sao lỗi này không làm hỏng kết luận cách ly

Cần tách bạch, vì trực giác dễ đi sai hướng ở đây.

Hàm bị siết **ném lỗi** khi thiếu phạm vi. Nó không trả về toàn bộ kho. Nghĩa là
chế độ hỏng là **đóng**, không phải **mở**: đường gọi thiếu phạm vi thì gãy, chứ
không lặng lẽ đọc dữ liệu của đơn vị khác.

Đây chính là điều mà thiết kế của hàm nhắm tới, và lượt đo vừa xác nhận nó hoạt
động trên hai đường đi thật. Một hàm rơi về "đọc tất cả" khi thiếu phạm vi sẽ
cho ra đúng hai lượt gọi ấy **thành công** — và đó mới là thảm hoạ, vì không ai
biết dữ liệu vừa lọt.

Nói cách khác: hai lỗi trên là **cái giá của việc đóng một lỗ rò**, và chúng
hiện diện dưới dạng dễ thấy nhất có thể. Chúng cần được sửa, nhưng chúng không
làm suy yếu khẳng định về cách ly — chúng củng cố nó.

---

## Ảnh hưởng tới thiết kế phép đo

Đối chứng dương của P0-B phải chứng minh chủ sở hữu **thật sự đọc, sửa và xoá
được** tài nguyên của chính mình. Vế "sửa" gặp hai trở ngại khác hẳn nhau, và
việc phân biệt chúng là bắt buộc:

| thao tác | kết cục | bản chất |
|---|---|---|
| tạo lớp trong đơn vị của mình | lỗi máy chủ | **lỗi** — tài liệu này |
| sửa lớp của đơn vị mình | từ chối vì thiếu quyền | **thiết kế** — xem dưới |
| xoá mẫu của chính mình | thành công | đối chứng dương đạt |

Trở ngại thứ hai không phải lỗi: mọi thao tác sửa/xoá lớp đều gác sau quyền quản
trị **nền tảng**, không phải vai trong đơn vị. Một đơn vị do đó không tự quản trị
được danh mục lớp của mình. Đó là một quan sát kiến trúc riêng, đã ghi ở
[FINDING_P0B_platform_admin_crosses_tenants.md](FINDING_P0B_platform_admin_crosses_tenants.md).

Hệ quả cho phép đo: vế "sửa" của đối chứng dương được mang bởi thao tác **xoá
mẫu của chính mình**, và thao tác sửa lớp được chuyển sang nhóm "đúng đơn vị,
sai quyền" — nơi mà bị từ chối là kết cục **đúng**, không phải kết cục trượt.

---

## Việc cần làm, sau kỳ bảo vệ

Truyền phạm vi vào bảy nơi gọi. Với hai đường bảo trì đọc toàn kho một cách hợp
lệ (đề bạt danh mục dùng chung, phân loại lại phương ngữ), đường đúng là gọi
biến thể đọc-toàn-kho đã có sẵn — nó được đặt tên dài và lộ liễu chính vì mục
đích ấy.

Không gộp vào một bản vá duy nhất: bảy nơi thuộc bốn ngữ cảnh phạm vi khác nhau,
và một bản vá gộp sẽ phải đoán phạm vi cho ít nhất ba trong số đó.

---

## Đính chính con số: mười một, không phải bảy

Bản đầu của tài liệu này ghi "bảy nơi gọi". Con số ấy sai, và cách nó sai đáng
ghi lại hơn bản thân con số.

Lệnh tìm kiếm dựng ra danh sách bị cắt bởi một giới hạn số dòng, và con số cắt
cụt được chép thẳng vào đây mà không ai đếm lại. Bốn nơi bị bỏ sót — trong đó có
**nơi nặng nhất cả nhóm**: một điểm cuối trả bảng lớp cho nhận dạng, đọc toàn kho
trên một đường **request**, không phải đường bảo trì.

Đây là lần thứ hai trong cùng một ngày một con số cắt cụt suýt vào tài liệu, và
là cùng họ lỗi với mọi bộ đếm tự chế khác trong kho này. Bài học không phải "cẩn
thận hơn" mà là: **một con số dùng để kết luận thì phải đến từ một lệnh không có
giới hạn hiển thị.**

## Phân loại mười một nơi

Sáu nơi đọc toàn kho một cách **hợp lệ**, và nay gọi biến thể có tên dài để ý
định lộ ra ngay tại chỗ đọc: dựng lại tệp chỉ mục nhãn, đồng bộ bù hàng thiếu lúc
khởi động, phân loại lại phương ngữ, xuất bảng tính, đề bạt nhãn dùng chung, và
bộ soát dữ liệu.

Gọi hàm có phạm vi rồi bỏ trống tham số **không** phải lựa chọn tương đương: bỏ
trống không phân biệt được với quên.

Năm nơi cần phạm vi thật:

| nơi | vì sao |
|---|---|
| bảng lớp cho nhận dạng | **đường request**; rò danh mục, và lệch chỉ số lớp so với mô hình |
| kế hoạch cân bằng | đếm mẫu của mọi tổ chức rồi đề xuất bù cho lớp tổ chức khác |
| bộ đếm mẫu theo lớp | cùng lý do |
| bản đồ siêu dữ liệu lớp | cùng lý do |
| công cụ sinh mẫu tăng cường | **GHI** xuống cây theo chủ sở hữu; đọc toàn kho là đổ mẫu vào cây tổ chức khởi tạo |

## Kết cục

Đã sửa đủ mười một nơi tại `47a8846`. Bảy ca kiểm độc lập từng bắt lỗi này nay
xanh, cùng bốn ca khác thất bại gián tiếp qua tầng HTTP.

Phát biểu đúng cho phần kết quả chức năng và phần thảo luận:

> Việc siết phạm vi tổ chức cho kho tệp đã đóng đường lùi xuyên tổ chức, nhưng
> một số đường xử lý yêu cầu chưa truyền đủ ngữ cảnh tổ chức, khiến chức năng
> tương ứng thất bại **theo hướng đóng**.

Câu **không** được viết: *cách ly tổ chức làm hỏng hệ thống.* Câu đúng: *việc
chuyển sang phạm vi tổ chức hỏng-theo-hướng-đóng chưa hoàn tất ở một số nơi gọi,
tạo ra hồi quy khả dụng nhưng không tạo ra phơi lộ xuyên tổ chức.*
