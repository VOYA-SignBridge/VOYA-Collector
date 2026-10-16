# Đồng ý đóng góp dữ liệu ngôn ngữ ký hiệu

**Phiên bản 2026-08-08** · Có hiệu lực từ ngày công bố trên hệ thống

> **Bản thảo kỹ thuật.** Chưa qua rà soát pháp chế. Phải được thẩm định trước
> khi thu thập dữ liệu từ người ngoài nhóm nghiên cứu.

---

Văn bản này hỏi bạn **trước lần đóng góp đầu tiên**, không phải lúc bạn tạo tài
khoản. Đó là chủ ý: gộp nó vào lúc đăng ký sẽ thu được một chữ ký cho việc mà
người ký chưa hình dung. Ở đây, "đóng góp" nghĩa là **quay hình bàn tay, thân
trên và khuôn mặt của một con người** vào một bộ dữ liệu nghiên cứu. Đó là thứ
phải hỏi khi bạn đang đứng trước máy quay, không phải khi đang điền email.

---

## 1. Chúng tôi ghi lại chính xác cái gì

Khi bạn thực hiện một ký hiệu trước máy quay:

**Video gốc.** Toàn khung hình, gồm mặt bạn, trong vài giây.

**Toạ độ điểm mốc.** Từ video, hệ thống trích ra vị trí của các điểm trên bàn
tay, thân trên và khuôn mặt theo từng khung hình. Đây là thứ mô hình học từ đó.

**Siêu dữ liệu.** Ký hiệu nào, thời điểm, thiết bị, tài khoản nào ghi, và một
**mã người ký**.

## 2. "Mã người ký" là gì và nó KHÔNG làm được gì

Mỗi người xuất hiện trong dữ liệu được gán một mã, ví dụ `S042`. Mã này giữ
nguyên qua các buổi ghi để nhóm nghiên cứu chia tập huấn luyện và tập kiểm thử
sao cho **cùng một người không nằm ở cả hai bên** — nếu không, mô hình học thuộc
người thay vì học ký hiệu và kết quả đo được sẽ đẹp một cách sai sự thật.

**Mã người ký không phải mã ẩn danh.** Nói thẳng: nó liên kết mọi mẫu của bạn
lại với nhau, và trong video có mặt bạn. Ai xem được dữ liệu thì nhận ra bạn.
Bảo vệ ở đây đến từ việc **kiểm soát ai xem được**, không đến từ việc dữ liệu
không định danh.

## 3. Đây là dữ liệu sinh trắc học

Hình ảnh khuôn mặt và dáng chuyển động của bạn là **dữ liệu sinh trắc học** —
nhóm dữ liệu cá nhân nhạy cảm theo pháp luật Việt Nam về bảo vệ dữ liệu cá nhân.

Hệ quả thực tế, và đây là lý do văn bản này tồn tại riêng:

- chúng tôi **phải** hỏi bạn một cách tách bạch, không gộp vào điều khoản chung;
- bạn **phải** đồng ý một cách chủ động, không phải bằng một ô đã tích sẵn;
- bạn **có thể** rút lại bất cứ lúc nào, không cần nêu lý do;
- việc bạn từ chối **không** ảnh hưởng tới quyền dùng phần còn lại của hệ thống.

## 4. Dữ liệu của bạn dùng vào việc gì

**Có:**

- huấn luyện mô hình nhận dạng ngôn ngữ ký hiệu tiếng Việt;
- đo và so sánh chất lượng các mô hình;
- xây dựng bộ dữ liệu phục vụ nghiên cứu của tổ chức bạn.

**Chỉ khi bạn đồng ý riêng bằng văn bản:**

- đưa vào bộ dữ liệu công bố cùng bài báo khoa học;
- chia sẻ cho nhóm nghiên cứu bên ngoài tổ chức bạn;
- dùng làm ví dụ minh hoạ trong bài trình bày hay tài liệu quảng bá.

**Không bao giờ:**

- nhận dạng danh tính bạn, hay dùng làm dữ liệu cho hệ thống nhận diện khuôn mặt;
- bán hoặc cho thuê;
- chuyển cho bên thứ ba ngoài các dịch vụ hạ tầng đã nêu ở *Chính sách quyền
  riêng tư* mục 3.

## 5. Ai xem được

Thành viên tổ chức bạn, theo vai trò. Cách ly giữa các tổ chức được cưỡng chế ở
tầng cơ sở dữ liệu.

Nhóm vận hành có quyền truy cập kỹ thuật để vận hành và khắc phục sự cố.

## 6. Giữ bao lâu

Cho tới khi tổ chức bạn xoá dữ liệu, hoặc cho tới khi bạn rút lại chấp thuận
này.

## 7. Rút lại

Rút bất cứ lúc nào, qua quản trị viên tổ chức hoặc trực tiếp với nhóm CTU
SignBridge.

**Điều xảy ra khi bạn rút:**

- các mẫu gắn với mã người ký của bạn được đánh dấu loại khỏi bộ dữ liệu dùng
  cho huấn luyện và công bố về sau;
- tệp và video của bạn được xoá theo yêu cầu.

**Điều chúng tôi phải nói thật:** một mô hình **đã huấn luyện xong** trước lúc
bạn rút thì không tách phần đóng góp của bạn ra khỏi nó được. Trọng số của mạng
nơ-ron không phải một cơ sở dữ liệu để xoá từng dòng. Chúng tôi có thể ngừng
dùng mô hình đó và huấn luyện lại từ bộ dữ liệu đã loại dữ liệu của bạn — và sẽ
làm vậy nếu bạn yêu cầu — nhưng bản đã có thì không "gỡ" được.

Chúng tôi nói điều này ra thay vì hứa một thứ không giữ được.

## 8. Bạn không bắt buộc phải đồng ý

Từ chối văn bản này thì bạn vẫn dùng được hệ thống để xem dữ liệu, quản lý danh
mục và chạy nhận dạng. Bạn chỉ không đóng góp mẫu mới.

## 9. Người dưới 18 tuổi

Cần thêm đồng ý của người giám hộ. Xem văn bản *Đồng ý của người giám hộ*.

## 10. Liên hệ

Nhóm nghiên cứu CTU SignBridge, Trường Đại học Cần Thơ.
