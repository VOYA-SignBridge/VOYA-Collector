# CHƯƠNG 3: THIẾT KẾ VÀ CÀI ĐẶT GIẢI PHÁP

*Chương này trình bày hệ thống đã được thiết kế và cài đặt như thế nào, và quan
trọng hơn — **vì sao** thiết kế theo cách đó chứ không theo cách khác. Mỗi quyết
định lớn đi kèm bảng so sánh phương án và tiêu chí chọn. Chương 1 nói hệ thống
phải làm gì; chương này nói nó làm bằng cách nào.*

---

## 1. Tổng quan hệ thống

### 1.1 Bối cảnh sản phẩm

CTU.SignBridge là một **nền tảng web đa tổ chức** để thu thập, tổ chức, quản lý và
hỗ trợ khai thác dữ liệu Ngôn ngữ Ký hiệu Việt Nam. Nhiều tổ chức — một trường,
một nhóm nghiên cứu, một doanh nghiệp — dùng chung **một bản triển khai duy
nhất**, nhưng dữ liệu của họ **được cô lập theo mặc định**: truy cập ra ngoài phạm
vi của mình chỉ hợp lệ qua cơ chế chia sẻ hoặc cấp quyền tường minh và có quản trị.

Cần khoanh phạm vi ngay tại đây. Đối tượng thiết kế và đánh giá của luận văn là
**phân hệ thu thập và quản lý dữ liệu** trong nền tảng đó, không phải toàn bộ
CTU.SignBridge; các thành phần huấn luyện và nhận dạng được xem là bên tiêu thụ
dữ liệu ở hạ nguồn.

Ba đặc điểm phân biệt nền tảng này với một ứng dụng thu dữ liệu thông thường:

* **Dữ liệu rời trình duyệt ở dạng đã trích đặc trưng.** Điểm mốc bàn tay được
  trích ngay tại máy người dùng bằng WebAssembly, nên với đường thu qua webcam,
  video thô **không bắt buộc rời khỏi máy đó**.
* **Ranh giới tổ chức do cơ sở dữ liệu cưỡng chế**, không do lập trình viên nhớ
  viết điều kiện lọc.
* **Danh mục từ vựng là tạo tác có phiên bản và có chữ ký số**, không phải một
  bảng tra cứu sửa tự do.

Hệ thống đặt trong bối cảnh sau:

```
┌────────────────────────── Bên ngoài ──────────────────────────┐
│  Người ký (webcam)   Kho lưu trữ ngoài   Dịch vụ gửi tin      │
│  Ứng dụng bên thứ ba  Máy ghi nguồn sự thật                    │
└───────┬──────────────────┬──────────────────┬─────────────────┘
        │                  │                  │
┌───────▼──────────────────▼──────────────────▼─────────────────┐
│                     CTU.SignBridge                             │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ Giao diện│  │ Dịch vụ   │  │ Xử lý nền│  │ Suy luận      │ │
│  │ web      │  │ ứng dụng  │  │ + huấn   │  │ thời gian thực│ │
│  │          │  │           │  │ luyện    │  │               │ │
│  └──────────┘  └───────────┘  └──────────┘  └───────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Cơ sở dữ liệu quan hệ · Hàng đợi · Kho tệp · Quan trắc  │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

> ### ▣ HÌNH 3-1 — Bối cảnh sản phẩm và các bên liên quan
> **Loại:** sơ đồ ngữ cảnh (context diagram) · **Công cụ:** draw.io
> **Phải thể hiện:** hộp hệ thống ở giữa; sáu tác nhân hệ thống S1–S6 ở ngoài
> kèm chiều mũi tên dữ liệu; bốn nhóm tác nhân người ở bên trái; **ranh giới hệ
> thống vẽ rõ** để thấy kho lưu trữ ngoài và dịch vụ gửi tin nằm ngoài.
> **Chú thích:** *Hình 3-1: Bối cảnh sản phẩm CTU.SignBridge.*

### 1.2 Tổng quan chức năng

Tám nhóm nghiệp vụ ở Chương 1 được cài đặt thành **26 bộ định tuyến API** với
**213 điểm cuối**, một giao diện đơn trang hơn 30 màn hình, và một bộ công cụ vận
hành chạy trên dòng lệnh.

*Bảng 3-9: Bộ định tuyến và số điểm cuối*

| Nghiệp vụ | Bộ định tuyến | Điểm cuối |
|---|---|:--:|
| NV1 Danh tính và quyền truy cập | `auth`, `verification`, `two_factor`, `legal`, `trial` | 34 |
| NV2 Thu thập và quản lý dữ liệu mẫu | `upload`, `dataset`, `label_sessions`, `jobs`, `dataset_exporter` | 38 |
| NV3 Danh mục từ vựng và phương ngữ | `classes`, `vocabulary` | 22 |
| NV4 Huấn luyện, đánh giá và suy luận | `training`, `experiments`, `inference`, `realtime_proxy`, `tts` | 31 |
| NV5 Tổ chức và đăng ký dịch vụ | `tenants`, `billing` | 28 |
| NV6 Quản trị người dùng và chính sách | `admin`, `legal_admin` | 34 |
| NV7 Vận hành hệ thống và nguồn sự thật | `sot_admin`, `health` | 13 |
| NV8 Hỗ trợ và tích hợp | `support`, `notifications`, `integrations` | 22 |
| | **Tổng** | **213** |

Cách đếm: số bộ trang trí phương thức HTTP trong `backend/app/routers/`. Con số
này lệch vài đơn vị so với số đường dẫn trong đặc tả OpenAPI, vì một hàm có thể
đăng ký nhiều phương thức trên cùng một đường dẫn. Nêu cách đếm ra để con số kiểm
chứng lại được.

---

## 2. Kiến trúc hệ thống

### 2.1 Các thành phần trong kiến trúc hệ thống

Hệ thống đóng gói theo container. Tệp khai báo triển khai định nghĩa **15 dịch
vụ**, trong đó một dịch vụ là container khởi tạo chạy một lần rồi thoát, còn lại
**14 dịch vụ chạy thường trực**.

| Nhóm | Dịch vụ | Vai trò |
|---|---|---|
| **Biên** | `nginx` | Cổng vào duy nhất; một điểm phục vụ cho cả giao diện lẫn API, nên trình duyệt không phải đối mặt với chính sách cùng nguồn |
| **Ứng dụng** | `frontend` | Giao diện đơn trang React, phục vụ tĩnh sau khi dựng |
| | `backend` | Dịch vụ API, xử lý toàn bộ nghiệp vụ đồng bộ |
| | `realtime_service` | Suy luận thời gian thực, tách riêng vì có vòng đời và nhu cầu GPU khác backend |
| **Xử lý nền** | `worker` | Thực thi tác vụ bất đồng bộ: trích đặc trưng, đồng bộ kho ngoài, dựng bản xem trước |
| | `celery-beat` | Bộ lập lịch: đối soát định kỳ, nhắc hạn, dọn dẹp |
| | `trainer` | Huấn luyện mô hình, chiếm GPU, tách riêng để không tranh chấp với `worker` |
| **Dữ liệu** | `postgres` | Cơ sở dữ liệu quan hệ; nơi cưỡng chế cách ly |
| | `redis` | Trung gian truyền tác vụ, bộ đếm hạn mức, bộ đệm phiên |
| | `pg-backup` | Sao lưu định kỳ |
| **Khởi tạo** | `sot-init` | Kéo và **xác minh chữ ký** danh mục trước khi bất kỳ dịch vụ nào chạy |
| **Quan trắc** | `prometheus` | Thu thập chỉ số |
| | `grafana` | Biểu đồ và **cảnh báo** |
| | `loki` | Kho nhật ký |
| | `promtail` | Thu gom nhật ký từ container |

**Một chi tiết kiến trúc đáng nói riêng:** `sot-init` thoát với mã lỗi chuyên biệt
sẽ **chặn toàn bộ hệ thống khởi động**. Đây là quyết định có chủ ý, không phải
hiệu ứng phụ: một máy không xác thực được danh mục thì không được phép phục vụ.
Thiết kế fail-closed ở đây trả giá bằng khả năng sẵn sàng để đổi lấy khả năng
không phục vụ dữ liệu sai.

**Ba lý do tách dịch vụ**, để phân biệt với việc tách vì mốt kiến trúc:

1. `trainer` tách khỏi `worker` vì **cạnh tranh tài nguyên**: một tác vụ huấn
   luyện chiếm GPU hàng giờ; nếu chung tiến trình, các tác vụ trích đặc trưng
   ngắn sẽ bị bỏ đói.
2. `realtime_service` tách khỏi `backend` vì **mô hình vòng đời khác nhau**: nó
   giữ mô hình đã nạp trong bộ nhớ và phục vụ kết nối dài, còn `backend` phục vụ
   yêu cầu ngắn và khởi động lại thường xuyên hơn.
3. `sot-init` tách ra vì nó phải chạy **trước** và **kết thúc** trước khi các dịch
   vụ khác bắt đầu — một quan hệ thứ tự, không phải một quan hệ gọi.

> ### ▣ HÌNH 3-2 — Kiến trúc triển khai
> **Loại:** sơ đồ triển khai · **Công cụ:** draw.io
> **Nguồn dựng:** `docker-compose.yml` + `docker-compose.prod.yml` + `docker-compose.gpu.yml`
> **Phải thể hiện:** 15 dịch vụ nhóm theo sáu nhóm trên; mạng nội bộ; các volume
> bền vững; **mũi tên phụ thuộc khởi động** từ `sot-init` tới `backend`/`worker`;
> GPU gắn vào `trainer` và `realtime_service`; `nginx` là cổng vào duy nhất từ
> ngoài.
> **Chú thích:** *Hình 3-2: Kiến trúc triển khai 15 dịch vụ container.*

### 2.2 Quá trình tương tác giữa các thành phần

Lấy nghiệp vụ trục chính — **thu một mẫu qua webcam** — làm ví dụ, vì nó chạm vào
gần như mọi thành phần.

```
Trình duyệt                Backend        Redis      Worker     Postgres   Kho ngoài
    │                         │             │          │           │           │
 1  │ trích điểm mốc          │             │          │           │           │
    │ (WebAssembly, tại máy)  │             │          │           │           │
 2  │──── POST mẫu ──────────►│             │          │           │           │
 3  │                         │─ kiểm đồng thuận + hạn mức ───────►│           │
 4  │                         │─ ghi bản ghi mẫu ─────────────────►│           │
 5  │                         │── đẩy tác vụ ►│         │           │           │
 6  │◄─── trả mã tác vụ ──────│             │          │           │           │
 7  │                         │             │◄─ lấy ──│           │           │
 8  │                         │             │          │─ ghi kho thô ─────────►│
 9  │                         │             │          │─ cắt cửa sổ, tăng cường│
10  │                         │             │          │─ chấm chất lượng       │
11  │                         │             │          │─ ghi tệp đặc trưng ───►│
12  │                         │             │          │─ cập nhật trạng thái ─►│
13  │◄─ hỏi trạng thái ──────►│─────────────────────────────────────►│           │
```

Ba điểm thiết kế lộ ra từ luồng này:

**Bước 1 quyết định toàn bộ phần còn lại.** Vì trích đặc trưng xảy ra trước bước
2, thứ đi qua mạng là một mảng số khoảng vài chục KiB thay vì một tệp video vài
MiB. Hệ quả dây chuyền: băng thông thấp hơn, kho lưu trữ nhỏ hơn, và **không có
video thô để rò rỉ**.

**Bước 6 trả về trước khi bước 7–12 xảy ra.** Người dùng không chờ. Đổi lại, giao
diện phải có đường hỏi trạng thái (bước 13) và phải xử lý được trạng thái "đang
xử lý" như một trạng thái hợp lệ chứ không phải một lỗi.

**Bước 8 xảy ra trước bước 9.** Bản thô được ghi **trước** mọi bước chuẩn hoá. Nếu
bước chuẩn hoá có lỗi, dữ liệu gốc vẫn còn để xử lý lại. Thứ tự này là một ràng
buộc thiết kế, không phải một chi tiết cài đặt.

> ### ▣ HÌNH 3-3 — Tương tác giữa các thành phần khi thu một mẫu
> **Loại:** sơ đồ tuần tự (sequence diagram)
> **Phải thể hiện:** sáu đường đời như sơ đồ trên; **đánh dấu rõ ranh giới đồng
> bộ / bất đồng bộ** ở bước 6; vòng lặp hỏi trạng thái ở bước 13; nhánh ngoại lệ
> "mất mạng ở bước 2 → giữ dữ liệu ở trình duyệt".
> **Chú thích:** *Hình 3-3: Trình tự tương tác khi thu một mẫu qua webcam.*

### 2.3 Cơ sở thiết kế ứng dụng

Bốn quyết định lớn định hình kiến trúc. Mỗi quyết định trình bày theo cùng một
khuôn: các phương án đã cân nhắc, tiêu chí, và lựa chọn.

#### 2.3.1 Cách ly dữ liệu giữa các tổ chức

*Bảng 3-1: So sánh ba mô hình cách ly dữ liệu đa tổ chức*

| Tiêu chí | Mỗi tổ chức một CSDL riêng | Mỗi tổ chức một lược đồ riêng | **Dùng chung lược đồ + cưỡng chế theo hàng** |
|---|---|---|---|
| Mức cách ly | Cao nhất | Cao | Trung bình – cao |
| Chi phí tài nguyên | Rất cao (n bản CSDL) | Cao | Thấp |
| Thay đổi cấu trúc | Phải chạy trên n bản | Phải chạy trên n lược đồ | Một lần |
| Truy vấn xuyên tổ chức (thống kê nền tảng) | Rất khó | Khó | Dễ, qua một phạm vi riêng |
| Rủi ro chính | Vận hành không xuể | Số lược đồ bùng nổ | **Rò dữ liệu nếu điều kiện lọc sót** |
| Phù hợp với RB-T1 (một máy chủ) | Không | Khó | **Có** |

**Chọn: dùng chung lược đồ, cưỡng chế theo hàng.** Ràng buộc RB-T1 loại hai
phương án đầu — một máy chủ 12 GB RAM không chạy nổi n bản cơ sở dữ liệu. Nhưng
lựa chọn này mang theo đúng rủi ro nguy hiểm nhất: **rò dữ liệu khi điều kiện lọc
sót**. Toàn bộ thiết kế bốn tầng dưới đây tồn tại để bịt rủi ro đó.

#### 2.3.2 Bốn tầng cưỡng chế cách ly

Đây là **đóng góp lõi** của luận văn. Bốn tầng, mỗi tầng bịt một lối vòng mà ba
tầng còn lại để hở.

**Tầng 1 — Cột phân biệt.** Mỗi bảng chịu ranh giới tổ chức mang một cột định
danh tổ chức. Cần thiết, nhưng một mình thì **chỉ là siêu dữ liệu**: không có gì
buộc truy vấn phải dùng nó.

**Tầng 2 — Chính sách bảo mật mức hàng.** Chính sách so sánh cột phân biệt với
một biến ngữ cảnh của phiên. Chi tiết quyết định nằm ở **dạng đọc biến**: hàm đọc
được gọi ở dạng "cho phép thiếu", nên khi biến chưa được gán, phép so sánh cho ra
giá trị NULL. **NULL không phải TRUE**, nên hàng không lọt qua chính sách. Đó
chính là cơ chế làm mệnh đề *"không khai báo tổ chức ⇒ 0 hàng"* thành đúng.

Nếu dùng dạng đọc "bắt buộc có", biến chưa gán sẽ ném lỗi — nghe có vẻ an toàn
hơn, nhưng thực tế biến mọi công việc nền hợp lệ thành lỗi hệ thống, và áp lực
vận hành sẽ đẩy người ta tới chỗ tắt chính sách. Fail-closed **im lặng** ở đây an
toàn hơn fail-closed ồn ào.

**Tầng 3 — Phạm vi giao dịch.** Biến ngữ cảnh được gán bằng lệnh **giới hạn trong
giao dịch**, trong một khối quản lý ngữ cảnh duy nhất của mã nguồn. Lệnh gán
thường (không giới hạn giao dịch) sẽ **dính lại trên kết nối** và rò sang yêu cầu
kế tiếp khi dùng bể kết nối. Đây là lỗi kinh điển của cặp "bảo mật mức hàng cộng
bể kết nối", và nó **không sinh ra thông báo lỗi nào** — chỉ có một người dùng
xui xẻo đọc được dữ liệu của người khác.

**Tầng 4 — Tách vai cơ sở dữ liệu.** Vai chạy của ứng dụng chỉ có quyền thao tác
dữ liệu; quyền thay đổi cấu trúc nằm ở một vai riêng. Lý do rất cụ thể: lệnh vô
hiệu hoá chính sách bảo mật mức hàng **là một lệnh thay đổi cấu trúc**. Một vai
vừa ghi được dữ liệu vừa chạy được lệnh cấu trúc thì **tự gỡ được vòng vây của
chính nó**, và bảo đảm biến thành lời khuyên.

Cần nói thêm: chỉ bật cờ "cưỡng chế cả với chủ sở hữu bảng" là **không đủ**, vì
cơ sở dữ liệu miễn trừ chính sách **vô điều kiện** cho vai siêu người dùng. Vai
chạy của ứng dụng vì thế không được là siêu người dùng, và điều đó phải kiểm được
bằng truy vấn siêu dữ liệu chứ không bằng niềm tin.

**Biến ngữ cảnh thứ hai** phục vụ công việc nền hợp lệ xuyên tổ chức: đối soát dữ
liệu lúc khởi động, tiến trình đọc nguồn sự thật, bảo trì theo lịch. Nó được làm
thành **một biến riêng biệt**, cố ý, chứ không phải một "giá trị tổ chức đặc
biệt". Lý do: nếu "hành động thay mọi tổ chức" là một giá trị của cùng biến tổ
chức, thì một lỗi gõ sai tên tổ chức có thể vô tình sinh ra đặc quyền đó. Tách
biến làm điều đó **không thể xảy ra do nhầm lẫn**.

> ### ▣ HÌNH 3-4 — Bốn tầng cưỡng chế cách ly tổ chức
> **Loại:** sơ đồ tầng · **Phải thể hiện:** bốn tầng xếp chồng; cạnh mỗi tầng ghi
> **lối vòng mà nó bịt** (tầng 1: không có; tầng 2: truy vấn quên lọc; tầng 3: rò
> ngữ cảnh qua bể kết nối; tầng 4: ứng dụng tự tắt chính sách); một mũi tên
> "tấn công" thử xuyên qua và bị chặn ở từng tầng.
> **Chú thích:** *Hình 3-4: Bốn tầng cưỡng chế cách ly và lối vòng mà mỗi tầng bịt.*

#### 2.3.3 Biểu diễn dữ liệu

*Bảng 3-2: So sánh phương án biểu diễn dữ liệu*

| Tiêu chí | Video thô | Khung ảnh đã trích | **Chuỗi điểm mốc bàn tay** |
|---|---|---|---|
| Dung lượng mỗi mẫu | MiB | trăm KiB | **hàng chục KiB** |
| Video rời khỏi máy người dùng | Bắt buộc | Bắt buộc | **Không bắt buộc** |
| Thông tin giữ lại | Đầy đủ | Đầy đủ theo khung | Chỉ hình học bàn tay |
| Trích lại đặc trưng khác về sau | Được | Được | **Không** |
| Chi phí tính toán ở máy chủ | Cao | Trung bình | **Thấp** (đã trích ở máy khách) |
| Rủi ro lộ diện người tham gia | Cao | Cao | **Thấp hơn** — nhưng *không phải* ẩn danh |

**Chọn: chuỗi điểm mốc bàn tay**, 126 chiều mỗi khung (21 điểm mốc × 3 toạ độ × 2
bàn tay), lưu ở định dạng mảng số có nén.

Hai điều phải nói thẳng kèm lựa chọn này:

* **Đây là một phép biến đổi có mất mát, và mất mát là một chiều.** Không lấy lại
  được video, nên cũng không trích lại được loại đặc trưng khác về sau. Nếu một
  nghiên cứu tương lai cần biểu cảm khuôn mặt, dữ liệu đã thu **không phục vụ
  được** — phải thu lại.
* **Không được lập luận "điểm mốc là ẩn danh".** Chuỗi điểm mốc không mang hình
  ảnh khuôn mặt, nhưng nó vẫn là dữ liệu về một con người cụ thể, và vẫn có thể
  quy về người đó khi ghép với siêu dữ liệu khác. Thuật ngữ dùng thống nhất trong
  quyển là **"không lộ diện"**, không phải "ẩn danh" [@wp29_anonymisation_2014].

#### 2.3.4 Tổ chức các bước xử lý

*Bảng 3-3: So sánh phương án tổ chức bước xử lý*

| Tiêu chí | Xử lý đồng bộ trong yêu cầu | Mỗi bước một tác vụ nền | **Gộp các bước vào một tác vụ nền** |
|---|---|---|---|
| Người dùng phải chờ | Có | Không | Không |
| Số lần chạm hàng đợi | 0 | Nhiều | 1 |
| Chạy lại từng bước riêng | — | Được | **Không** — chạy lại cả cụm |
| Trạng thái trung gian phải lưu | Không | Nhiều | **Ít** |
| Độ phức tạp vận hành | Thấp | **Cao** | Trung bình |

**Chọn: gộp các bước vào một tác vụ nền.** Đánh đổi được chấp nhận có ý thức: mất
khả năng chạy lại từng bước riêng, đổi lấy việc không phải quản lý một chuỗi
trạng thái trung gian. Với quy mô hiện tại — một máy chủ, một hàng đợi — chi phí
vận hành của phương án giữa lớn hơn giá trị nó mang lại.

**Giới hạn phải ghi:** vì cả cụm chạy lại cùng nhau, tính lũy đẳng phải bảo đảm ở
mức cụm. Hiện tại **chưa bảo đảm đồng đều**: bước ghi tệp đặc trưng chạy lại an
toàn, nhưng bước tải lên kho ngoài có thể tạo bản trùng. Đây là hạn chế đã biết,
nêu ở Chương 4 và ở phần Kết luận.

#### 2.3.5 Thẩm quyền ký trong cơ chế nguồn sự thật

*Bảng 3-4: So sánh phương án thẩm quyền ký*

| Tiêu chí | Không ký, tin vào kho lưu trữ | Mọi máy đều ký được | **Một máy phát hành duy nhất giữ khoá ký** |
|---|---|---|---|
| Phát hiện sửa đổi | Không | Có | **Có** |
| Xác định được ai sửa | Không | Có | **Có** |
| Rủi ro khoá bị lộ | — | **n lần** | 1 lần |
| Hợp nhất hai máy | Ghi đè lẫn nhau | Xung đột | **Một chiều, chỉ điền** |
| Chi phí vận hành | Thấp | Cao | Trung bình |

**Chọn: một máy phát hành duy nhất.** Máy đó giữ khoá riêng Ed25519
[@josefsson_edwards-curve_2017] và công bố các phiên bản bất biến của danh mục và
lược đồ. Máy chủ và các máy triển khai khác **chỉ đọc**: lúc khởi động, chúng kéo
bản mới nhất, kiểm chữ ký với khoá công khai đã ghi trong mã nguồn, rồi bảo đảm
cơ sở dữ liệu của mình là **tập cha** của bản đó — thêm cái thiếu, **không bao
giờ xoá**.

Ba tính chất đạt được, và phải phát biểu tách bạch vì chúng khác nhau:

| Tính chất | Nghĩa | Trạng thái |
|---|---|---|
| **Toàn vẹn** | Sửa được nhưng không giấu được | **Đạt** — bản kê băm SHA-256 toàn bộ tệp, chữ ký phủ bản kê |
| **Xác thực nguồn** | Biết ai ký, không chỉ biết "có chữ ký hợp lệ" | **Đạt** — hàm xác minh trả về **tên khoá đã đăng ký**, không trả về giá trị đúng/sai |
| **Đơn điệu phiên bản** | Bản mới không bị bản cũ ghi đè lùi | **Chưa cưỡng chế** — xem Chương 4 §5.5 |

*Một bài học thiết kế đáng ghi lại:* danh sách cột bắt buộc dùng để kiểm bản công
bố từng **thiếu sáu cột**. Hệ quả: một bản công bố có lược đồ thiếu vẫn **qua được
khâu xác minh**, rồi mới hỏng giữa chừng lúc nhập dữ liệu, khi ghi những cột mà
bản kê chưa từng hứa là có. Đây là ví dụ điển hình của "phép kiểm không phủ hết
thứ mà nó bảo vệ" — và nó là lý do phép đo ở Chương 4 phải chạy qua **đúng đường
tiêu thụ của ứng dụng**, không qua hàm trợ giúp.

#### 2.3.6 Năm nguyên lý thiết kế xuyên suốt

Năm nguyên lý dưới đây rút ra từ quá trình xây dựng, và chúng lặp lại ở nhiều chỗ
trong hệ thống:

1. **Thiếu ngữ cảnh thì dừng, không đoán.** Áp cho cách ly (không có tổ chức ⇒ 0
   hàng), cho danh mục (thiếu dữ liệu ⇒ dừng), cho nguồn sự thật (không xác minh
   được ⇒ không khởi động), cho nhật ký kiểm toán (không có phạm vi ⇒ từ chối
   ghi).
2. **Kế thừa lúc khởi tạo khác với rơi về lúc chạy.** Sao chép danh mục cộng đồng
   vào một tổ chức mới là **kế thừa** — xảy ra một lần, kết quả thuộc về tổ chức
   đó. Đọc danh mục cộng đồng khi tổ chức thiếu dữ liệu là **rơi về** — và bị cấm.
   Hai thứ trông giống nhau trên sơ đồ nhưng khác nhau hoàn toàn về hệ quả.
3. **Ngoại lệ phải là một phạm vi, không phải một lối đi vòng.** Công việc nền
   xuyên tổ chức cần một phạm vi được đặt tên và kiểm được, chứ không phải một
   giá trị đặc biệt lẫn trong dữ liệu thường.
4. **Tổng hợp cũng có thể rò rỉ.** Một điểm cuối trả về "số mẫu toàn nền tảng"
   không trả dữ liệu của ai cả, nhưng nếu một tổ chức chỉ có một thành viên thì
   con số tổng hợp ấy nói về đúng người đó. Mọi điểm cuối thống kê phải đi qua
   cùng cơ chế phạm vi.
5. **Không có đường quay ngược từ công khai vào riêng tư.** Dữ liệu đã công bố
   sang mặt phẳng dùng chung thì không rút lại được bằng một nút bấm. Vì thế
   đường công bố phải là một hành động tường minh, có xác thực lại, và có bản ghi.

---

## 3. Thiết kế dữ liệu

### 3.1 Mô hình dữ liệu

Lược đồ hiện có **57 bảng** và một khung nhìn. Trình bày cả 57 bảng trong một sơ
đồ quan hệ duy nhất là trình bày một thứ không ai đọc được. Chương này vì thế
trình bày mô hình theo **bảy nhóm mô-đun**, mỗi nhóm là một khối chức năng khép
kín; **mô hình mức khái niệm và mức vật lý đầy đủ nằm ở Phụ lục A**.

*Bảng 3-5: Bảy nhóm mô-đun dữ liệu*

| # | Nhóm mô-đun | Số bảng | Trả lời câu hỏi | Chịu ranh giới tổ chức |
|---|---|:--:|---|---|
| M1 | Danh tính & Truy cập | 7 | Anh là ai, phiên của anh còn hiệu lực không | Một phần |
| M2 | Tổ chức & Phân quyền | 9 | Anh thuộc tổ chức nào, với vai gì | Có |
| M3 | Kho dữ liệu mẫu | 6 | Dữ liệu ký hiệu và người ký ra nó | **Có — trọng tâm** |
| M4 | Danh mục & Registry | 11 | Được phép thu lớp nào, phiên bản danh mục nào | Có, trừ mặt phẳng cộng đồng |
| M5 | Huấn luyện & Mô hình | 3 | Dữ liệu thành mô hình như thế nào | Có |
| M6 | Dịch vụ tổ chức & Tích hợp | 11 | Gói cước, hạn mức, khoá API, hỗ trợ | Có |
| M7 | Pháp lý, Kiểm toán & Nền tảng | 10 | Ai đồng ý gì, ai làm gì, cấu hình nền tảng | Một phần |
| | **Tổng** | **57** | | |

Ba nhóm cần giải thích riêng vì chúng mang các quyết định thiết kế đáng bảo vệ.

#### M1 — Danh tính & Truy cập

Nhóm này **cố ý không phủ ranh giới tổ chức hoàn toàn**. Lý do: bảng tài khoản
phải truy vấn được **trước khi** biết tổ chức — chính lúc đăng nhập. Nếu bảng tài
khoản chịu chính sách bảo mật mức hàng theo tổ chức, thì truy vấn tìm tài khoản
lúc đăng nhập sẽ khớp 0 hàng, và hệ thống không đăng nhập được cho ai cả.

Điều này sinh ra một cái bẫy đã mắc **ba lần trong hai ngày**, và đáng viết vào
quyển vì nó là bài học thật: khi một truy vấn chạy **trước khi** biết tổ chức,
chính sách khớp 0 hàng, và mã ứng dụng đọc "0 hàng" thành **"không có gì"** thay
vì **"chưa có ngữ cảnh"**. Cách ly fail-closed ở tầng cơ sở dữ liệu vẫn có thể bị
tầng ứng dụng **diễn giải sai thành fail-open**.

Bảng trong nhóm: tài khoản; token làm mới; token đặt lại mật khẩu; mã xác thực;
bí mật TOTP; mã khôi phục; mã xác thực lại cho thao tác nhạy cảm.

> ### ▣ HÌNH 3-6 — Nhóm M1 và M2: Danh tính, Tổ chức và Phân quyền
> **Loại:** sơ đồ quan hệ thực thể rút gọn
> **Phải thể hiện:** 16 bảng của hai nhóm; lực lượng quan hệ; **đánh dấu bảng nào
> chịu chính sách bảo mật mức hàng** bằng một ký hiệu thống nhất; khung nhìn
> `tenant_members` vẽ bằng nét đứt để phân biệt với bảng thật.
> **Chú thích:** *Hình 3-6: Mô hình dữ liệu nhóm Danh tính, Tổ chức và Phân quyền.*

#### M2 — Tổ chức & Phân quyền

Nhóm này đã qua một lần tái cấu trúc đáng kể. Mô hình phân quyền ban đầu có nhiều
bảng rời rạc cho từng loại vai; bản hiện tại gộp về **một mô hình gán vai theo
phạm vi**: một bản ghi gán vai mang bốn thông tin — chủ thể, vai, **cấp phạm vi**,
và định danh phạm vi. Cấp phạm vi nhận bốn giá trị: hệ thống, tổ chức, không gian
làm việc, dự án.

Hệ quả đáng chú ý: bảng thành viên tổ chức không còn là một bảng, mà là một
**khung nhìn** trên lát cắt "cấp phạm vi = tổ chức" của bảng gán vai. Điều này giữ
được toàn bộ mã cũ đọc theo tên bảng đó, đồng thời đưa mọi gán vai về một chỗ.
Cái giá phải trả rất cụ thể: khung nhìn **không tạo chỉ mục được** và **không
nhận mệnh đề xử lý xung đột**, nên mọi đường ghi phải sửa để ghi vào bảng gốc.

**Giới hạn phải nêu thẳng:** hai cấp phạm vi dưới — không gian làm việc và dự án
— **có bảng nhưng chưa có bề mặt API**. Đối chiếu đặc tả OpenAPI: không có đường
dẫn nào chứa hai khái niệm này. Vì vậy chúng hiện là **cấu trúc dữ liệu, chưa
phải bề mặt vận hành**, và không có gì để kiểm chứng cách ly ở hai cấp đó từ bên
ngoài. Đây là lý do phát biểu chính thức trong quyển là *"kiến trúc hỗ trợ nhiều
cấp; cưỡng chế chứng minh được ở cấp hệ thống và cấp tổ chức"*.

#### M3 — Kho dữ liệu mẫu

Nhóm trọng tâm. Sáu bảng: mẫu, lớp, phiên thu, bản tải lên thô, người ký, bí danh
người ký.

Ba quyết định mô hình hoá đáng bảo vệ:

**Thứ nhất — người ký là một thực thể, không phải một cột.** Tài khoản thu mẫu và
người có bàn tay trong mẫu là hai vế khác nhau (Chương 1 §1.2). Tách người ký
thành thực thể riêng cho phép: gán lại người ký khi phát hiện sai, gắn đồng thuận
vào đúng chủ thể, và trả lời được câu "những dòng nào là của người này".

Đo được, và phải báo cáo: định danh người ký hiện phủ **43,4 %** số mẫu. Nghĩa là
hơn một nửa kho dữ liệu **không quy được về người ký**. Đây là kết quả nghiên cứu
về khoảng cách giữa mô hình đúng và dữ liệu lịch sử, không phải một khiếm khuyết
cần giấu.

**Thứ hai — khoá ngoại là khoá ghép có mang định danh tổ chức.** Quan hệ từ mẫu
tới lớp không đi qua một cột đơn, mà qua cặp (tổ chức, lớp). Lý do: một khoá
ngoại đơn cho phép mẫu của tổ chức A trỏ tới lớp của tổ chức B — cơ sở dữ liệu
không phản đối, vì khoá vẫn tồn tại. Khoá ghép làm việc đó **bất khả thi ở tầng
ràng buộc**, không phải ở tầng kiểm tra của ứng dụng. Truy vấn trực tiếp cơ sở dữ
liệu đang chạy ngày **17/08/2026**: **22 khoá ngoại ghép** trong tổng số **117
khoá ngoại**; danh sách các khoá ghép của nhóm này ở Phụ lục A §4.3.

**Thứ ba — định danh lớp gồm cả phương ngữ và vùng miền.** Khoá định danh lớp ở
tầng cơ sở dữ liệu gồm năm cột, trong khi tầng ứng dụng từng chỉ dùng bốn. Lệch
này có hậu quả thật: một chỉ mục cũ trên cơ sở dữ liệu sản xuất **cấm** hai biến
thể cùng nhãn khác vùng miền, và điều đó chặn việc nhập dữ liệu từ nguồn từ điển
quốc gia. Đây là ví dụ cho thấy mô hình dữ liệu và mô hình trong đầu lập trình
viên lệch nhau thì lỗi xuất hiện ở chỗ không ai ngờ.

**Ba quyết định trên cùng phục vụ một mục tiêu: giữ được nguồn gốc của dữ liệu.**
Mô hình dữ liệu bảo toàn nguồn gốc bằng cách tách ba loại thứ vốn hay bị gộp —
**đối tượng** được quản lý, **hoạt động** sinh ra chúng, và **chủ thể** gắn với
hoạt động đó. Trên đường thu, điều này có nghĩa là người ký, tài khoản vận hành,
phiên thu, bản tải lên thô, biểu diễn dẫn xuất và tư cách thành viên trong một
phiên bản bộ dữ liệu đều được mô hình hoá thành **quan hệ tường minh**, thay vì bị
dồn vào một trường "người tạo" duy nhất. Chuỗi kết quả:

```
Người ký → Phiên thu → Mẫu → Bản tải lên thô / Biểu diễn dẫn xuất → Phiên bản bộ dữ liệu
```

Thiết kế này theo các nguyên lý nguồn gốc trình bày ở Chương 2 §2.8.5; luận văn
**không tuyên bố** hiện thực đầy đủ mô hình dữ liệu W3C PROV, cũng không sinh tài
liệu hay giao diện trao đổi theo chuẩn đó. Điều được khẳng định hẹp hơn: mỗi mắt
xích trong chuỗi trên là một quan hệ truy vấn được, nên câu hỏi *"mẫu này từ đâu
ra, qua bước nào, do ai"* trả lời được bằng truy vấn chứ không bằng suy đoán.

Cần nói kèm giới hạn, đúng theo lập luận ở Chương 2 §2.6.2: mắt xích đầu — quan hệ
giữa mẫu và người ký — chỉ thiết lập được đáng tin tại thời điểm thu, và con số
**43,4 %** ở trên chính là phần dữ liệu mà mắt xích đó tồn tại. Với phần còn lại,
chuỗi nguồn gốc bị đứt ở đúng vị trí không dựng lại được.

> ### ▣ HÌNH 3-7 — Nhóm M3: Kho dữ liệu mẫu
> **Phải thể hiện:** sáu bảng và quan hệ; **vẽ rõ khoá ngoại ghép mang định danh
> tổ chức** (ghi cặp cột trên cạnh); phân biệt quan hệ "tài khoản thu" với quan
> hệ "người ký" bằng hai cạnh khác nhau từ bảng mẫu — đây là điểm phải nhìn thấy
> được từ hình.
> **Chú thích:** *Hình 3-7: Mô hình dữ liệu nhóm Kho dữ liệu mẫu.*

#### M4 — Danh mục & Registry: ba mặt phẳng

Nhóm này cài đặt mô hình ba mặt phẳng:

```
Danh mục hệ thống ──sao chép MỘT LẦN──► Danh mục của tổ chức ──ghim──► Bộ dữ liệu
 (cấu hình, quản trị nền tảng)           (tổ chức tự sửa)              (bất biến, có mã băm)
```

Luật xuyên suốt: **lúc chạy KHÔNG bao giờ rơi ngược về mặt phẳng cộng đồng**;
thiếu dữ liệu thì **dừng**, không suy đoán.

Ba lỗi có thật đã thúc đẩy thiết kế này, và cả ba đáng đưa vào phần phân tích vấn
đề của quyển:

1. Danh sách hồ sơ nhận dạng gắn cứng ở hai nơi và đã lệch nhau (6 mục so với 5)
   → **7 lớp bị loại khỏi bước chia dữ liệu trong im lặng**.
2. Số hiệu phiên bản danh mục là một bộ đếm bị ghi đè, và ảnh chụp là một tệp bị
   ghi đè → "bộ dữ liệu ghim phiên bản 2" **không thực hiện được**, vì nội dung
   phiên bản 2 biến mất ngay khi phiên bản 3 được ghi.
3. Không có khái niệm thành viên tổ chức → hoặc không tổ chức nào tự quản được,
   hoặc mọi quản trị viên nền tảng thành biên tập viên của mọi tổ chức.

Một phân biệt phải giữ rõ trong quyển: **"đã đăng ký" không đồng nghĩa "huấn
luyện được"**. Một lớp có đủ mẫu nhưng người ký chưa đồng ý ở mức tương ứng thì
với đường phát hành nghiên cứu, nó là một lớp **rỗng**.

> ### ▣ HÌNH 3-8 — Nhóm M4: Danh mục ba mặt phẳng
> **Phải thể hiện:** ba mặt phẳng xếp theo chiều dọc; mũi tên sao chép **một
> chiều** từ cộng đồng sang tổ chức, có nhãn "một lần, lúc khởi tạo"; một mũi tên
> **gạch chéo** thể hiện đường rơi ngược bị cấm; quan hệ ghim phiên bản từ bộ dữ
> liệu tới một phiên bản danh mục cụ thể.
> **Chú thích:** *Hình 3-8: Ba mặt phẳng danh mục và luật không rơi ngược.*

> ### ▣ HÌNH 3-5 — Mô hình dữ liệu theo nhóm mô-đun
> **Loại:** sơ đồ khối · **Phải thể hiện:** bảy khối M1–M7 với số bảng của từng
> khối; các cạnh giữa khối thể hiện quan hệ chính (M2→M3 ranh giới tổ chức,
> M4→M3 lớp, M3→M5 dữ liệu huấn luyện, M7→M3 đồng thuận chi phối phát hành);
> **tô nền khác nhau cho khối chịu và không chịu ranh giới tổ chức**.
> **Chú thích:** *Hình 3-5: Kiến trúc mô hình dữ liệu theo bảy nhóm mô-đun.*

### 3.2 Danh mục các bảng dữ liệu

Bảng dưới đây liệt kê tên và vai trò của toàn bộ 57 bảng theo nhóm. **Chi tiết
từng cột, kiểu dữ liệu, ràng buộc và chỉ mục nằm ở Phụ lục A.**

*Bảng 3-6: Danh mục bảng dữ liệu theo nhóm*

| Nhóm | Bảng | Vai trò |
|---|---|---|
| **M1** | `users` | Tài khoản: định danh, mã băm mật khẩu, cờ quản trị nền tảng, trạng thái |
| | `refresh_tokens` | Phiên đăng nhập: token làm mới, thiết bị, địa chỉ IP, thời điểm thu hồi |
| | `password_reset_tokens` | Token đặt lại mật khẩu, dùng một lần, có hạn |
| | `verification_codes` | Mã xác thực địa chỉ liên hệ, hai kênh |
| | `user_totp` | Bí mật xác thực hai yếu tố |
| | `user_recovery_codes` | Mã khôi phục dùng một lần |
| | `user_action_passcodes` | Mã xác thực lại cho thao tác nhạy cảm |
| **M2** | `tenants` | Tổ chức: ranh giới cách ly cao nhất, trạng thái quản trị và trạng thái thương mại |
| | `workspaces`, `projects` | Hai cấp phạm vi bên trong tổ chức — **có bảng, chưa có bề mặt API** |
| | `roles`, `permissions`, `role_permissions` | Định nghĩa vai và quyền |
| | `role_assignments` | Gán vai theo phạm vi: chủ thể × vai × cấp phạm vi × định danh phạm vi |
| | `tenant_members` *(khung nhìn)* | Lát cắt "cấp phạm vi = tổ chức" của bảng gán vai |
| | `tenant_invitations` | Lời mời: địa chỉ nhận, vai dự kiến, hạn dùng, trạng thái |
| **M3** | `samples` | **Mẫu dữ liệu** — bảng trung tâm; siêu dữ liệu, chỉ số chất lượng, đường dẫn tệp |
| | `classes` | Lớp từ vựng: nhãn, ngôn ngữ, phương ngữ, vùng miền, số bàn tay yêu cầu |
| | `capture_sessions` | Phiên thu: gom nhiều mẫu cùng một lượt ngồi trước camera |
| | `raw_uploads` | Bản tải lên thô, ghi **trước** chuẩn hoá |
| | `signers` | **Người ký** — chủ thể dữ liệu |
| | `signer_aliases` | Bí danh, phục vụ gộp hai bản ghi người ký trùng |
| **M4** | `languages`, `regions` | Danh mục ngôn ngữ và vùng miền |
| | `dialects`, `dialect_aliases` | Phương ngữ của tổ chức và bí danh sau khi gộp |
| | `recognition_profiles` | Hồ sơ nhận dạng: nhóm lớp phục vụ cùng một mô hình |
| | `vocabulary_groups` | Nhóm từ vựng |
| | `vocabulary_registry_meta` | Siêu dữ liệu danh mục của tổ chức |
| | `registry_versions` | **Phiên bản danh mục bất biến** — thứ bộ dữ liệu ghim vào |
| | `community_dialects`, `community_profiles`, `community_versions` | Mặt phẳng cộng đồng, nguồn để sao chép một lần |
| **M5** | `training_jobs` | Tác vụ huấn luyện: phạm vi, tham số, trạng thái, **phiên bản danh mục đã ghim** |
| | `training_job_classes` | Tập lớp thực sự tham gia sau khi qua ba cổng chặn |
| | `training_metrics` | Chỉ số theo chu kỳ huấn luyện |
| **M6** | `plans` | Gói cước và hạn mức |
| | `tenant_subscriptions` | Đăng ký dịch vụ của tổ chức: kỳ hạn, trạng thái, ân hạn |
| | `tenant_usage_daily` | Mức sử dụng theo ngày — nguồn cho việc **tính tiền** |
| | `tenant_exports`, `tenant_purges` | Yêu cầu xuất dữ liệu và yêu cầu dọn sạch |
| | `api_keys` | Khoá API: lưu **mã băm**, không lưu khoá |
| | `webhook_endpoints`, `webhook_deliveries` | Điểm nhận sự kiện và lịch sử gửi |
| | `support_tickets`, `support_messages` | Phiếu hỗ trợ và tin nhắn trong phiếu |
| | `notifications` | Thông báo trong ứng dụng |
| **M7** | `legal_documents` | Văn bản pháp lý đã công bố — **bất biến**, có mã băm nội dung |
| | `legal_document_drafts` | Bản thảo, sửa được |
| | `legal_document_events` | Lịch sử vòng đời văn bản |
| | `user_consents` | Chấp thuận của **tài khoản**, trỏ tới cặp (loại, phiên bản) |
| | `signer_consents` | Đồng thuận của **người ký** — thứ chi phối đường phát hành |
| | `audit_log` | Nhật ký kiểm toán bền vững |
| | `platform_settings` | Cấu hình nền tảng |
| | `sot_authorized_keys` | Khoá công khai được tin cậy của máy phát hành |
| | `google_sheets_sync_status` | Trạng thái phản chiếu sang bảng tính ngoài |
| | `event_outbox` | Hộp thư đi cho sự kiện gửi ra ngoài |

**Về mức độ phủ của cơ chế cách ly:** 34 bảng mang cột định danh tổ chức; 32 bảng
bật chính sách bảo mật mức hàng, và **cả 32 bảng đó đều bật cờ cưỡng chế với chủ
sở hữu bảng** (tỉ lệ 32/32). Độ phủ 32/34 ≈ 94,1 %. Hai bảng còn lại mang cột
định danh tổ chức nhưng không bật chính sách — lý do và đánh giá rủi ro ghi ở Phụ
lục A.

### 3.3 Mối liên hệ giữa các đối tượng

*Bảng 3-7: Các quan hệ then chốt*

| Quan hệ | Lực lượng | Ghi chú thiết kế |
|---|---|---|
| Tổ chức — Tài khoản | n : m, qua bảng gán vai | Một người thuộc nhiều tổ chức với vai khác nhau ở mỗi tổ chức |
| Tổ chức — Mẫu | 1 : n | Ranh giới cách ly; cưỡng chế bằng chính sách bảo mật mức hàng |
| Lớp — Mẫu | 1 : n, **khoá ghép** | Khoá ngoại mang cả định danh tổ chức, nên không trỏ chéo tổ chức được |
| Người ký — Mẫu | 1 : n, **khoá ghép** | Phủ 43,4 %; phần còn lại không quy kết được |
| Phiên thu — Mẫu | 1 : n | Một lượt ngồi trước camera sinh nhiều mẫu |
| Phương ngữ — Lớp | 1 : n, **khoá ghép** | Phương ngữ là **một phần định danh lớp**, không phải thuộc tính phụ |
| Phiên bản danh mục — Tác vụ huấn luyện | 1 : n | Ghim phiên bản: điều kiện để tái lập được thí nghiệm |
| Văn bản pháp lý — Chấp thuận | 1 : n, khoá tới cặp (loại, phiên bản) | Văn bản bất biến, nên chấp thuận trỏ tới nội dung xác định |
| Người ký — Đồng thuận | 1 : n | Đồng thuận có phiên bản; rút là rút thật |
| Gói cước — Đăng ký dịch vụ | 1 : n | Trạng thái thương mại tách khỏi trạng thái quản trị |

### 3.4 Ba miền dữ liệu và ranh giới giữa chúng

Ngoài phân nhóm theo mô-đun, dữ liệu còn chia theo **quyền quản trị**. Ba miền
này không lồng nhau, và nhầm lẫn giữa chúng là nguồn của nhiều lỗi.

*Bảng 3-8: Ba miền dữ liệu*

| | Miền của tổ chức | Miền dùng chung | Miền danh mục hệ thống |
|---|---|---|---|
| Ai sửa được | Tổ chức sở hữu | Không ai sửa trực tiếp; chỉ nhận qua công bố | Quản trị nền tảng |
| Ai đọc được | Chỉ tổ chức đó | Mọi tổ chức | Mọi tổ chức, chỉ đọc |
| Cưỡng chế bằng | Chính sách bảo mật mức hàng | Quy trình công bố tường minh | Chữ ký số |
| Ví dụ | mẫu, lớp, phiên thu | dữ liệu đã công bố cho cộng đồng | phương ngữ chuẩn, lược đồ |
| Đường vào | thu nhận | **công bố một chiều** | công bố có ký |
| Đường ra | xuất dữ liệu tổ chức | không có | không có |

**Ranh giới quan trọng nhất: giá trị `default` không phải là miền dùng chung.**
Tổ chức mang định danh `default` là tổ chức **mồi** — nơi dữ liệu lịch sử của hệ
thống tiền thân nằm lại. Nó là một tổ chức bình thường về mọi mặt cách ly. Coi nó
là "dữ liệu chung" là mở một lỗ hổng đúng bằng toàn bộ dữ liệu lịch sử.

Một cái bẫy cụ thể trong mã: hàm chuẩn hoá định danh tổ chức trả về `default` khi
nhận chuỗi rỗng. Hệ quả: một hàm kiểm tra viết sau bước chuẩn hoá sẽ **không bao
giờ thấy chuỗi rỗng**, và trở thành mã chết. Nguyên tắc rút ra: **kiểm tham số
thô trước khi chuẩn hoá**.

### 3.5 Hai mặt phẳng lưu trữ

Ràng buộc RB-D2 để lại một cấu hình không lý tưởng và phải nói thẳng: **nguồn sự
thật của kho mẫu là một tệp CSV**, còn cơ sở dữ liệu quan hệ là **bản sao để truy
vấn**.

Đây là di sản từ hệ thống tiền thân, không phải một thiết kế được chọn. Hệ quả và
cách xử lý:

| Rủi ro | Cách xử lý |
|---|---|
| Hai mặt phẳng lệch nhau | Tác vụ đối soát định kỳ theo chiều CSV → cơ sở dữ liệu |
| Đường ghi tệp **không** chịu chính sách bảo mật mức hàng | Cách ly ở mặt phẳng tệp cưỡng chế bằng **cấu trúc thư mục theo tổ chức** cộng kiểm tra ở tầng ứng dụng — mức bảo đảm **thấp hơn** mặt phẳng cơ sở dữ liệu, và phải phát biểu đúng như vậy |
| Kiểm thử ghi nhầm vào dữ liệu thật | Bộ kiểm thử từng ghi vào tệp nguồn sự thật thật; đã bổ sung chốt chặn |

**Phát biểu đúng mức về cách ly, phải giữ nhất quán:** cách ly được **cưỡng chế ở
tầng cơ sở dữ liệu** cho mọi tài nguyên nằm trong cơ sở dữ liệu; với tài nguyên
nằm trên hệ tệp, cách ly dựa vào cấu trúc lưu trữ và kiểm tra ở tầng ứng dụng.
Phép đo ở Chương 4 đo **cả hai mặt phẳng**, và đó là lý do nó được gọi là phép đo
*xuyên kho*.

---

## 4. Thiết kế chức năng

Phần này trình bày thiết kế của các chức năng trục chính. Mỗi mục theo cùng khuôn:
luồng xử lý, các quyết định thiết kế, và giới hạn.

### 4.1 Tổ chức mã nguồn

```
backend/app/
  routers/        26 bộ định tuyến, 213 điểm cuối
  storage/        tầng truy cập dữ liệu; nơi đặt ngữ cảnh tổ chức
  processing/     trích đặc trưng, cắt cửa sổ, tăng cường, chấm chất lượng
  sot/            công bố và xác minh nguồn sự thật
  training/       điều phối huấn luyện
frontend/src/
  pages/          hơn 30 màn hình
  components/     thành phần dùng lại
  i18n/           chuỗi hiển thị, không có chuỗi cứng trong mã
scripts/          công cụ vận hành: sao lưu, đối soát, kiểm độ tươi triển khai
```

Quy mô, đếm lại ngày **17/08/2026**: **61.097 dòng** mã Python trong 162 tệp ở
phần dịch vụ, **48.074 dòng** TypeScript trong 221 tệp ở phần giao diện, và
**41.760 dòng** mã kiểm thử trong 151 tệp.

Tỉ lệ mã kiểm thử trên mã dịch vụ là **0,68 : 1**. Con số này là hệ quả trực tiếp
của một nguyên tắc ở Chương 4 §2.2 chứ không phải một mục tiêu tự đặt: mỗi khẳng
định trung tâm phải có một phản chứng, nên phần lớn hợp đồng được ghim bằng
**hai** ca kiểm thử thay vì một.

**Một quy ước có ý nghĩa kiến trúc:** ngữ cảnh tổ chức được đặt ở **đúng một khối
quản lý ngữ cảnh** trong tầng truy cập dữ liệu. Không có đường nào khác đặt được
ngữ cảnh này. Đây là điều làm tầng 3 của cơ chế cách ly (§2.3.2) khả thi — nếu
mỗi hàm tự đặt ngữ cảnh theo cách riêng, không ai bảo đảm được lệnh gán luôn giới
hạn trong giao dịch.

### 4.2 Thu nhận và xử lý bất đồng bộ

**Luồng xử lý một bản ghi:**

```
Nhận yêu cầu
   ├─ kiểm đồng thuận hiệu lực      → thiếu ⇒ chặn ghi, điều hướng chấp thuận
   ├─ kiểm hạn mức tổ chức          → vượt ⇒ từ chối, nêu hạn mức gói
   ├─ ghi bản ghi mẫu (trạng thái `pending`)
   └─ đẩy tác vụ vào hàng đợi, trả mã tác vụ
        ↓  (bất đồng bộ)
Tiến trình nền
   ├─ ghi kho thô                    ← TRƯỚC mọi chuẩn hoá
   ├─ cắt cửa sổ trượt (60 khung, bước nhảy 2)
   ├─ tăng cường dữ liệu
   ├─ chấm chất lượng: độ đầy đủ, độ rung, tỉ lệ hiện diện của tay
   ├─ ghi tệp đặc trưng
   ├─ cập nhật bản ghi mẫu (trạng thái `ready` + chỉ số)
   └─ đẩy tác vụ đồng bộ kho ngoài (có thử lại)
```

**Bốn nhóm công việc chạy nền:** trích đặc trưng và chuẩn hoá; đồng bộ kho lưu trữ
ngoài; dựng bản xem trước; bảo trì theo lịch (đối soát, nhắc hạn, sao lưu, dọn
dẹp).

**Hai chỉ số chất lượng và khả năng tái lập.** Độ đầy đủ tính lại được từ tệp đặc
trưng; độ rung thì **không**, vì nó phụ thuộc vào chuỗi thời gian trước khi chuẩn
hoá. Đây là một phân biệt phải giữ khi báo cáo: một chỉ số tái lập được và một
chỉ số không tái lập được không có cùng giá trị chứng minh. Ngoài ra, **độ đầy đủ
bằng 0 không có nghĩa tệp rỗng** — nó có nghĩa không phát hiện được bàn tay nào,
và hai điều đó khác nhau.

**Giới hạn về độ tin cậy, phải nêu:** cơ chế thử lại **không đồng đều** giữa bốn
nhóm công việc, và tính lũy đẳng **chưa bảo đảm** cho việc tạo tài nguyên và tải
đối tượng lên kho ngoài. Kết luận đúng mức cho cam kết tương ứng là *"đạt về năng
lực, có hạn chế về độ tin cậy"* — không phải *"đạt một phần"* về năng lực.

> ### ▣ HÌNH 3-9 — Luồng xử lý bất đồng bộ của một bản ghi
> **Phải thể hiện:** ranh giới đồng bộ/bất đồng bộ; thứ tự **ghi kho thô trước
> chuẩn hoá**; ba nhánh lỗi (không phát hiện được tay, vượt hạn mức, kho ngoài
> không phản hồi) và hành vi tương ứng.
> **Chú thích:** *Hình 3-9: Luồng xử lý bất đồng bộ của một bản ghi thu.*

> ### ▣ HÌNH 3-10 — Vòng đời trạng thái của một mẫu
> **Loại:** máy trạng thái · **Phải thể hiện:** `pending → processing → ready`,
> nhánh `failed`, nhánh `deleted` (xoá mềm) → `purged` (xoá hẳn) và cạnh khôi
> phục ngược từ `deleted` về `ready`.
> **Chú thích:** *Hình 3-10: Máy trạng thái vòng đời một mẫu dữ liệu.*

### 4.3 Danh tính, phiên và kiểm soát truy cập

**Cổng mặc định từ chối.** Kiểm soát truy cập đặt ở tầng trung gian, **trước** khi
yêu cầu tới bộ định tuyến. Một điểm cuối mới viết ra mà tác giả quên khai báo
quyền thì **tự động yêu cầu xác thực** — ngược với mô hình "mỗi điểm cuối tự khai
báo", nơi quên khai báo nghĩa là để ngỏ.

Thiết kế này từng bịt **tám lỗ công khai** đã tồn tại, trong đó có một điểm cuối
làm lộ mười tên tài khoản thật. Bài học: danh sách ngoại lệ công khai phải được
**rà soát định kỳ**, vì nó là chỗ duy nhất còn lại có thể sai.

**Ba mức thu hồi phiên**, không được lẫn: thu hồi một phiên (đăng xuất trên một
thiết bị); thu hồi mọi phiên của một tài khoản (đổi mật khẩu); thu hồi theo biện
pháp quản trị (đình chỉ tài khoản).

**Một bài học về lọc dữ liệu trả về:** bỏ khai báo mô hình trả về của một điểm
cuối tương đương với **gỡ bộ lọc bảo mật** — và đã làm rò mã băm mật khẩu ra
ngoài trong một lần sửa. Mô hình trả về ở đây không phải chuyện tài liệu hoá; nó
là một cơ chế bảo vệ.

**Xác thực hai yếu tố** cài đặt theo chuẩn TOTP và **kiểm bằng vector thử của tiêu
chuẩn**, không chỉ kiểm bằng "đăng nhập được". Phân biệt này quan trọng: một cài
đặt sai lệch múi giờ vẫn cho đăng nhập được với ứng dụng sinh mã cùng lỗi, nhưng
không tương thích với ứng dụng chuẩn.

### 4.4 Đồng thuận và khuôn khổ pháp lý

Đây là phần khác biệt nhất so với một công cụ thu dữ liệu thông thường.

**Thang ba mức đồng thuận**, gắn với **người ký**, không gắn với tài khoản. Mỗi
đường phát hành dữ liệu đọc mức đồng thuận trước khi lấy mẫu; mẫu không đủ mức
thì **không xuất hiện** trong bản phát hành đó.

**Bốn nghĩa của "thu hồi", và hệ thống chỉ thi hành nghĩa thứ hai:**

| # | Nghĩa | Đã thi hành? |
|---|---|---|
| 1 | Thu hồi quyền truy cập của một người | Có — qua cơ chế cách ly và vai |
| 2 | Gỡ khỏi các bản phát hành **mới** | **Có** — bốn đường dữ liệu đều qua cổng đồng thuận |
| 3 | Xoá khỏi lưu trữ | Không — là thao tác vận hành, làm tay |
| 4 | Thu hồi giấy phép **đã cấp** cho bên thứ ba | Không — cần cơ chế pháp lý |

Hứa "xoá là biến mất hoàn toàn" là hứa nghĩa 3 và 4 trong khi chỉ làm nghĩa 2.
Giao diện nói thẳng điều này, và **có kiểm thử ghim đúng câu chữ đó** — để một
lần sửa giao diện về sau không vô tình biến một giới hạn thành một lời hứa.

**Văn bản pháp lý bất biến sau khi công bố**, cưỡng chế bằng ràng buộc ở tầng cơ
sở dữ liệu chứ không bằng kiểm tra ở ứng dụng. Lý do đã nêu ở Chương 1 §2.6. Một
cờ riêng tách "sửa lỗi chính tả" khỏi "đổi phạm vi xử lý dữ liệu"; chỉ loại thứ
hai buộc chấp thuận lại.

### 4.5 Nguồn sự thật ký số

**Luồng công bố** (trên máy phát hành):

```
Dựng tạo tác ──► tính SHA-256 từng tệp ──► viết bản kê ──► ký bản kê (Ed25519)
                                                              │
                                                    đẩy lên kho lưu trữ ngoài
```

**Luồng xác minh** (trên mọi máy khác, lúc khởi động):

```
Kéo bản công bố
   ├─ tính lại mã băm, đối chiếu bản kê      → lệch ⇒ DỪNG
   ├─ kiểm chữ ký phủ bản kê                 → hỏng/thiếu ⇒ DỪNG
   ├─ tra khoá ký trong danh sách tin cậy    → không tin cậy ⇒ DỪNG
   └─ hợp nhất theo nguyên tắc CHỈ ĐIỀN, KHÔNG XOÁ
```

Hợp đồng xác minh có **bốn vế**, và chúng không thay thế được cho nhau:

```
Tạo tác hợp lệ = Toàn vẹn ∧ Chữ ký hợp lệ ∧ Người ký được tin cậy ∧ Chính sách phiên bản hợp lệ
```

Vế thứ ba là chỗ dễ bỏ sót nhất: một kẻ tấn công dựng dữ liệu khác, tính mã băm
đúng, viết bản kê đúng, rồi **tự ký bằng khoá của hắn**. Chữ ký ấy hợp lệ về mật
mã. Nếu hệ thống chỉ hỏi *"chữ ký có hợp lệ không"* mà không hỏi *"hợp lệ theo
khoá nào"* thì toàn vẹn đúng nhưng thẩm quyền sai. Cài đặt ở đây trả về **tên
khoá đã đăng ký** thay vì một giá trị đúng/sai, nên "ai ký" là một phần của kết
quả xác minh.

**Vế thứ tư là giới hạn đã biết.** Hệ thống chấp nhận một bản công bố có số hiệu
phiên bản thấp hơn bản đang dùng. Tài nguyên mới hơn không bị xoá — nguyên tắc
chỉ-điền bảo vệ điều đó — nhưng giá trị dùng chung **bị ghi đè lùi**. Bằng chứng
và đánh giá ở Chương 4 §5.5.

> ### ▣ HÌNH 3-11 — Cơ chế công bố và xác minh nguồn sự thật
> **Phải thể hiện:** hai luồng trên đặt cạnh nhau; **ba điểm DỪNG** đánh dấu nổi
> bật; ranh giới máy phát hành (có khoá riêng) và máy tiêu thụ (chỉ có khoá công
> khai); nguyên tắc chỉ-điền vẽ bằng mũi tên một chiều vào cơ sở dữ liệu.
> **Chú thích:** *Hình 3-11: Cơ chế công bố và xác minh nguồn sự thật ký số.*

### 4.6 Huấn luyện và ba cổng chặn

*Bảng 3-10: Ba cổng chặn huấn luyện*

| Cổng | Hỏi gì | Áp ở đâu | Hỏng thì hậu quả |
|---|---|---|---|
| Đồng thuận | Người ký cho phép dùng ở mức phát hành này không? | Lúc **chọn** mẫu | Phát hành vượt phạm vi được phép |
| Sàn số mẫu mỗi lớp | Lớp này đủ mẫu để chia tập không? | **Trước** khi đánh chỉ số lớp | Tập kiểm thử rỗng; chỉ số vô nghĩa |
| Hạn mức tổ chức | Tổ chức còn hạn mức tính toán không? | Lúc **xếp hàng** | Một tổ chức chiếm hết GPU chung |

Ba cổng hỏi ba câu khác nhau và **không thay thế được cho nhau**. Một chi tiết
thứ tự có hậu quả thật: **sàn số mẫu phải áp trước khi đánh chỉ số lớp**. Nếu
đánh chỉ số trước rồi mới loại lớp, chỉ số lớp sẽ nhảy cóc, và mô hình huấn luyện
trên một không gian nhãn khác với không gian nhãn lúc suy luận — một lỗi không
sinh ra thông báo nào, chỉ sinh ra kết quả sai.

Phân biệt thứ hai đáng giữ: **lọc lúc chia tập** khác **từ chối lúc chạy**. Lọc
là loại lớp không đủ điều kiện và tiếp tục; từ chối là dừng cả tác vụ. Hệ thống
làm cả hai, ở hai chỗ khác nhau, và phải nói rõ chỗ nào làm gì — nếu không, người
dùng sẽ tưởng mô hình được huấn luyện trên tập lớp mình chọn.

**Ghim phiên bản danh mục** vào bản ghi tác vụ là điều kiện để tái lập: chạy lại
tác vụ sáu tháng sau vẫn dùng đúng tập nhãn của lần đầu, kể cả khi danh mục đã
thay đổi.

> ### ▣ HÌNH 3-12 — Luồng huấn luyện và ba cổng chặn
> **Phải thể hiện:** ba cổng theo đúng thứ tự áp dụng; nhánh "loại lớp và tiếp
> tục" tách khỏi nhánh "từ chối cả tác vụ"; bước ghim phiên bản danh mục.
> **Chú thích:** *Hình 3-12: Luồng huấn luyện và ba cổng chặn.*

### 4.7 Nhận dạng thời gian thực

Đường nhận dạng nối đủ chặng: trình duyệt trích điểm mốc → gửi qua kết nối dài →
dịch vụ suy luận nạp mô hình **đang phục vụ** → trả nhãn kèm độ tin cậy → tuỳ
chọn đọc thành tiếng.

**Phân biệt phải giữ:** *phiên bản mới nhất* không phải *phiên bản đang phục vụ*.
Một mô hình vừa huấn luyện xong chưa phục vụ ai cho tới khi được **thăng hạng** —
một hành động tường minh của quản trị nền tảng, có bản ghi, và đảo ngược được.

**Phát biểu đúng mức, phải giữ nhất quán:** hệ thống **không** "nhận dạng ngôn ngữ
ký hiệu Việt Nam". Nó phục vụ nhận dạng cho **các miền từ vựng có mô hình đã đăng
ký**. Và độ tin cậy của một lượt suy luận đơn lẻ **không phải** một chỉ số chất
lượng — nó là đầu ra của một lượt chạy, không phải kết quả của một phép đánh giá.

> ### ▣ HÌNH 3-13 — Kiến trúc nhận dạng thời gian thực
> **Phải thể hiện:** trình duyệt · kết nối dài · dịch vụ suy luận · mô hình đang
> phục vụ trong bộ nhớ · đường nạp nóng khi thăng hạng; **tách rõ** đường dùng
> thử của khách vãng lai (có giới hạn số phút mỗi ngày).
> **Chú thích:** *Hình 3-13: Kiến trúc đường nhận dạng thời gian thực.*

### 4.8 Vận hành, quan trắc và sao lưu

**Quan trắc ba tầng:** chỉ số (Prometheus), biểu đồ và cảnh báo (Grafana), nhật ký
(Loki + Promtail). Cảnh báo **sống ở Grafana**, không có thành phần quản lý cảnh
báo riêng — một quyết định hợp với quy mô một máy chủ.

Hai bài học vận hành đáng đưa vào quyển:

* **Nhãn phân loại nhật ký phải ít.** Đặt định danh tổ chức làm nhãn phân loại
  sinh ra số chuỗi nhật ký bằng số tổ chức nhân số dịch vụ, và làm hệ thống nhật
  ký sập. Thông tin phân biệt phải nằm ở siêu dữ liệu có cấu trúc, không nằm ở
  nhãn.
* **Giá trị đặc biệt để tránh suy luận sai.** Một chỉ số trả về `-1` mang nghĩa
  *"không đo được"*, khác hẳn `0` nghĩa là *"đo được và bằng không"*. Không phân
  biệt hai giá trị này thì biểu đồ sẽ vẽ một đường bằng phẳng ở đáy và không ai
  biết hệ thống đang mù.

**Sao lưu:** nguyên tắc *một bản sao lưu chưa diễn tập khôi phục là một bản sao
lưu chưa tồn tại*. Có chế độ diễn tập chạy được. Hai bài học: thứ tự thao tác
phải là **kết xuất trước, nén sau**; và công cụ liệt kê nội dung tệp sao lưu
**không** phát hiện được tệp bị cụt — phải kiểm bằng phương pháp đọc hết nội dung.

**Kiểm chứng độ tươi triển khai:** công cụ riêng bắt ba kiểu lệch giữa mã đang
chạy và mã nguồn. Lý do tồn tại là một sự cố thật đã nêu ở Chương 1 §2.7.

---

## 5. Giao diện người dùng

Giao diện là ứng dụng đơn trang, hơn 30 màn hình, chia ba khu vực theo quyền:
khu vực người dùng, khu vực tổ chức, và console quản trị nền tảng.

Ba quy ước thiết kế giao diện được giữ nhất quán:

* **Bộ biểu tượng đồng nhất** — 70 biểu tượng vector, **không dùng emoji** trong
  giao diện. Emoji hiển thị khác nhau giữa các hệ điều hành và không đổi màu theo
  chủ đề.
* **Không có chuỗi cứng trong mã.** Mọi chuỗi hiển thị đi qua lớp đa ngôn ngữ, và
  độ phủ được kiểm bằng công cụ trong cổng trước triển khai. Bài học: độ phủ này
  từng được báo cáo là 100 % **sai hai lần** — công cụ đo bỏ sót các chuỗi nằm
  trong biểu thức điều kiện và trong chuỗi mẫu.
* **Vỏ console quản trị không phải hàng rào quyền.** Việc một trang nằm dưới
  đường dẫn quản trị không tự nó chặn ai; quyền vẫn kiểm ở tầng dịch vụ. Nhầm hai
  thứ này là một lỗ hổng kinh điển.

> ### ▣ HÌNH 3-14 — Giao diện thu mẫu trực tiếp
> **Loại:** ảnh chụp màn hình · **Phải thể hiện:** khung camera có vẽ chồng điểm
> mốc bàn tay; bảng chọn lớp – ngôn ngữ – phương ngữ; chỉ báo số bàn tay yêu cầu;
> nút thu và vùng xem lại.
> **Chú thích:** *Hình 3-14: Màn hình thu mẫu trực tiếp với điểm mốc bàn tay vẽ
> chồng theo thời gian thực.*

> ### ▣ HÌNH 3-15 — Giao diện danh mục lớp và chi tiết lớp
> **Phải thể hiện:** danh sách lớp kèm số mẫu; màn chi tiết một lớp với danh sách
> phiên thu, chỉ số chất lượng và thao tác quản trị.
> **Chú thích:** *Hình 3-15: Màn hình danh mục lớp và chi tiết một lớp.*

> ### ▣ HÌNH 3-16 — Console quản trị
> **Phải thể hiện:** thanh bên ba tầng (nền tảng / tổ chức / cài đặt); một trang
> tiêu biểu, ví dụ trang nhật ký kiểm toán hoặc trang quản lý tổ chức.
> **Chú thích:** *Hình 3-16: Console quản trị nền tảng.*

---

## 6. Tổng kết chương

Chương này đã trình bày kiến trúc 15 dịch vụ, mô hình dữ liệu 57 bảng theo bảy
nhóm mô-đun, và thiết kế của các chức năng trục chính. Bốn quyết định lớn đều
được đặt cạnh các phương án bị loại, kèm tiêu chí chọn.

Đóng góp thiết kế trung tâm là **bốn tầng cưỡng chế cách ly** ở §2.3.2: mỗi tầng
bịt một lối vòng mà ba tầng còn lại để hở, và tầng thứ tư — tách vai cơ sở dữ liệu
— là tầng biến cơ chế từ *lời khuyên* thành *bảo đảm*.

Ba giới hạn thiết kế đã được nêu thẳng trong chương, không giấu sang phần Kết
luận: hai cấp phạm vi dưới chưa có bề mặt vận hành (§3.1, M2); tính lũy đẳng chưa
đồng đều ở đường xử lý nền (§4.2); và đơn điệu phiên bản của nguồn sự thật chưa
được cưỡng chế (§4.5).

Chương 4 kiểm chứng những gì chương này khẳng định, bằng các phép đo có khả năng
thất bại.
