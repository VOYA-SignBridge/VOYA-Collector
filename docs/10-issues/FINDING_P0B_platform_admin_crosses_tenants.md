# Phát hiện trong lúc đo P0-B: cờ quản trị nền tảng gộp hai thẩm quyền

**Trạng thái:** ĐANG MỞ — quan sát kiến trúc, không phải lỗi cài đặt
**Phát hiện lúc:** 16/08/2026, khi dựng đối chứng dương cho P0-B
**Thuộc bản mã:** `19a8f75`, ảnh chụp mã `1961904ccb07ab25`

---

## Điều đã quan sát được

Tài khoản đo được gieo với cờ quản trị nền tảng, và cờ ấy được thêm vào vì một
lý do hẹp: cổng **quyền sở hữu** đứng trước cổng **phạm vi đơn vị**, nên nếu
không có tài khoản vượt được cổng thứ nhất một cách hợp lệ thì cổng thứ hai
không bao giờ bị kiểm tới.

Đo dưới chính tài khoản ấy — thuộc đơn vị A — cho kết quả sau, tái lập được:

| thao tác nhắm vào một đơn vị KHÁC | kết cục |
|---|---|
| đọc hồ sơ đơn vị | thành công |
| liệt kê toàn bộ đơn vị trên hệ thống | thành công |
| **xoá đơn vị hệ thống dự trữ** | **thành công** |

Lượt xoá là xoá mềm và đã được khôi phục ngay trên cơ sở dữ liệu đo. Không có
dữ liệu vận hành nào bị chạm: toàn bộ lượt đo chạy trên cơ sở dữ liệu test, bằng
vai quyền tối thiểu, trên một cây dữ liệu dùng-một-lần.

---

## Vì sao đây không phải "cách ly bị thủng"

Cờ quản trị nền tảng **có nghĩa là** thẩm quyền trên toàn nền tảng. Một tài
khoản mang nó xoá được đơn vị khác là hành vi đúng thiết kế, không phải rò rỉ.

Vấn đề nằm ở chỗ khác, và nó nghiêm trọng theo một kiểu khác: **cờ ấy gộp hai
thẩm quyền hoàn toàn khác nhau vào một bit.**

    miễn kiểm quyền sở hữu       (cần cho phép đo, và cho vận hành hằng ngày)
    thẩm quyền trên MỌI đơn vị   (không cần, và không nên đi kèm)

Không có cách nào cấp cái thứ nhất mà không cấp luôn cái thứ hai. Đó là một vi
phạm nguyên tắc đặc quyền tối thiểu ở cấp mô hình quyền, chứ không phải một chỗ
quên trong mã.

---

## Vì sao điều này suýt làm hỏng phép đo

Đây là phần đáng giá nhất của phát hiện, và nó thuộc về phương pháp chứ không
thuộc về sản phẩm.

Nếu ma trận đối kháng chạy bằng tài khoản mang cờ ấy, thì mọi thao tác xuyên đơn
vị trong đó **không đo cách ly đơn vị**. Nó đo năng lực của quản trị viên nền
tảng — một thứ vốn dĩ được phép xuyên đơn vị. Hai hệ quả, cả hai đều sai:

* các thao tác **thành công** sẽ bị chấm thành "vi phạm cách ly", trong khi
  chúng là hành vi đúng thiết kế — báo động giả;
* và tệ hơn, tỉ lệ vi phạm công bố ra sẽ là một con số đo **sai đối tượng**,
  nhưng trông hoàn toàn hợp lý trên bảng.

Đây đúng là họ lỗi mà cả vòng đo này được dựng để chặn: *một bộ đo cho ra con số
hợp lý về một thứ nó không đo*. Lần này nó bị bắt vì đối chứng dương buộc phải
chạy trước, và vì tài khoản đo bị kiểm lại danh tính trước khi bắn.

Lượt đo chính thức vì thế chạy bằng **tài khoản đơn vị thường**, không mang cờ
quản trị nền tảng. Tài khoản ấy vẫn vượt được cổng quyền sở hữu một cách hợp lệ,
vì cây dữ liệu ghi đúng chủ sở hữu cho từng mẫu — nên lý do ban đầu để cần cờ
quản trị đã không còn.

---

## Quan sát kèm theo: đơn vị không tự quản trị được danh mục của mình

Khi rà lại các cổng quyền trên nhóm điểm cuối danh mục lớp, hiện trạng là:

| nhóm thao tác | cổng |
|---|---|
| tạo lớp mới | vai biên tập của đơn vị |
| sửa, xoá, khôi phục, xoá vĩnh viễn lớp | **quản trị nền tảng** |

Nghĩa là một tổ chức thuê dịch vụ **không sửa hay xoá được lớp của chính mình**
— mọi thao tác ấy phải qua quản trị viên nền tảng. Với một hệ thống nhiều tổ
chức, đây là một khoảng trống mô hình quyền đáng kể: nó buộc nhà vận hành nền
tảng phải can thiệp vào dữ liệu của khách hàng cho những việc thường ngày.

Ghi nhận ở đây vì nó ảnh hưởng trực tiếp tới cách phát biểu kết luận về phân
quyền theo vai: phần "theo vai trong đơn vị" hiện chỉ phủ **thao tác tạo**.

---

## Ranh giới của phát hiện này

Không khẳng định rằng cờ quản trị nền tảng bị cấp sai cho ai đó trong vận hành
thật. Phát hiện chỉ nói về **hình dạng của mô hình quyền**: một bit gộp hai thẩm
quyền, và không có đường cấp riêng lẻ.

Việc tách bit ấy thành hai quyền độc lập là thay đổi mô hình quyền, không phải
một bản vá — và nó phải chờ tới khi mặt phẳng phân quyền mới chuyển từ chế độ
đối chiếu sang chế độ cưỡng chế.
