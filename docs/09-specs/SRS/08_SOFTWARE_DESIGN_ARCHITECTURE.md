# 8. Thiết kế phần mềm — Kiến trúc ứng dụng (Application Architecture)

---

## 8.1 Sơ đồ kiến trúc tổng thể

```
┌────────────────────────── BÊN NGOÀI ──────────────────────────┐
│  Người ký (webcam)   Kho lưu trữ ngoài   Dịch vụ gửi tin      │
│  Ứng dụng bên thứ ba  Máy ghi nguồn sự thật                   │
└───────┬──────────────────┬──────────────────┬─────────────────┘
        │                  │                  │
┌───────▼──────────────────▼──────────────────▼─────────────────┐
│                     CTU.SignBridge                             │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────────┐ │
│  │ Giao diện│  │ Dịch vụ   │  │ Xử lý nền│  │ Suy luận      │ │
│  │ web      │  │ ứng dụng  │  │ + huấn   │  │ thời gian thực│ │
│  │ (React)  │  │ (FastAPI) │  │ luyện    │  │               │ │
│  └──────────┘  └───────────┘  └──────────┘  └───────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  PostgreSQL · Redis · Kho tệp · Prometheus/Grafana/Loki  │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

## 8.2 Hai mô hình kiến trúc chồng lên nhau

Giống bản SRS mẫu, kiến trúc của hệ thống này cũng đọc được ở **hai lớp mô hình
khác nhau**, và hai lớp trả lời hai câu khác nhau.

### 8.2.1 Mô hình ba tầng — cho quan hệ Máy khách ↔ Máy chủ

| Tầng | Trong hệ thống này | Công nghệ |
|---|---|---|
| **Tầng trình bày** | Ứng dụng đơn trang chạy trong trình duyệt; **kèm một phần xử lý dữ liệu thật** — trích điểm mốc bàn tay bằng WebAssembly | React 19 + TypeScript, MediaPipe Hands |
| **Tầng nghiệp vụ** | Dịch vụ API đồng bộ, tiến trình nền bất đồng bộ, dịch vụ suy luận | FastAPI, Celery, PyTorch |
| **Tầng dữ liệu** | Cơ sở dữ liệu quan hệ (nơi cưỡng chế cách ly), hàng đợi/bộ đệm, kho tệp, kho ngoài | PostgreSQL, Redis, hệ tệp, Google Drive/Sheets |

**Một khác biệt so với mô hình ba tầng cổ điển, và nó có hệ quả kiến trúc:** tầng
trình bày ở đây **không chỉ trình bày**. Nó chạy bước trích đặc trưng — bước tốn
tính toán nhất trong đường thu. Vì thế "máy khách mỏng" không phải mô tả đúng, và
yêu cầu về CPU của máy người dùng là một yêu cầu thật (NFR-P2).

Toàn bộ ba tầng chạy trên **một máy chủ vật lý duy nhất** (RB-T1), đóng gói bằng
Docker Compose, đặt sau `nginx` làm cổng vào duy nhất, dưới đường dẫn cơ sở
`/voya`.

### 8.2.2 Mô hình tách theo trách nhiệm — cho phía máy chủ

Backend không theo MVC (không có tầng View phía máy chủ — giao diện là ứng dụng
riêng). Nó chia theo **trách nhiệm**:

| Lớp | Thư mục | Trách nhiệm |
|---|---|---|
| **Router** | `backend/app/routers/` | Nhận yêu cầu HTTP, kiểm định đầu vào bằng Pydantic, khai báo **mô hình trả về** (đây là một cơ chế bảo vệ, không phải tài liệu hoá) |
| **Service** | rải trong `app/` | Nghiệp vụ: cổng đồng thuận, cổng hạn mức, ba cổng huấn luyện, luật danh mục |
| **Storage** | `backend/app/storage/` | Truy cập dữ liệu; **nơi duy nhất đặt ngữ cảnh tổ chức** |
| **Processing** | `backend/app/processing/` | Trích đặc trưng, cắt cửa sổ, tăng cường, chấm chất lượng |
| **SoT** | `backend/app/sot/` | Công bố và xác minh nguồn sự thật |
| **Training** | `backend/app/training/` | Điều phối huấn luyện |

**Một quy ước có ý nghĩa kiến trúc:** ngữ cảnh tổ chức được đặt ở **đúng một khối
quản lý ngữ cảnh** trong tầng Storage. Không có đường nào khác đặt được ngữ cảnh
này. Đây là điều làm tầng cưỡng chế thứ ba (§8.4) khả thi — nếu mỗi hàm tự đặt
ngữ cảnh theo cách riêng, không ai bảo đảm được lệnh gán luôn giới hạn trong phạm
vi giao dịch.

---

## 8.3 Bốn quyết định kiến trúc lớn

Mỗi quyết định trình bày theo cùng một khuôn: phương án đã cân nhắc, tiêu chí, và
lựa chọn.

### 8.3.1 Mô hình cách ly dữ liệu đa tổ chức

| Tiêu chí | Mỗi tổ chức một CSDL riêng | Mỗi tổ chức một lược đồ riêng | **Dùng chung lược đồ + cưỡng chế theo hàng** |
|---|---|---|---|
| Mức cách ly | Cao nhất | Cao | Trung bình – cao |
| Chi phí tài nguyên | Rất cao (n bản CSDL) | Cao | **Thấp** |
| Thay đổi cấu trúc | Phải chạy trên n bản | Phải chạy trên n lược đồ | **Một lần** |
| Truy vấn xuyên tổ chức | Rất khó | Khó | **Dễ, qua một phạm vi riêng** |
| Rủi ro chính | Vận hành không xuể | Số lược đồ bùng nổ | **Rò dữ liệu nếu điều kiện lọc sót** |
| Phù hợp RB-T1 (một máy chủ) | Không | Khó | **Có** |

**Chọn: dùng chung lược đồ, cưỡng chế theo hàng.** Ràng buộc RB-T1 loại hai
phương án đầu — một máy chủ 12 GB RAM không chạy nổi n bản cơ sở dữ liệu. Nhưng
lựa chọn này mang theo **đúng rủi ro nguy hiểm nhất**: rò dữ liệu khi điều kiện
lọc sót. Toàn bộ thiết kế bốn tầng ở §8.4 tồn tại để bịt rủi ro đó.

### 8.3.2 Biểu diễn dữ liệu

| Tiêu chí | Video thô | Khung ảnh đã trích | **Chuỗi điểm mốc bàn tay** |
|---|---|---|---|
| Dung lượng mỗi mẫu | MiB | trăm KiB | **hàng chục KiB** |
| Video rời khỏi máy người dùng | Bắt buộc | Bắt buộc | **Không bắt buộc** |
| Thông tin giữ lại | Đầy đủ | Đầy đủ theo khung | Chỉ hình học bàn tay |
| Trích lại đặc trưng khác về sau | Được | Được | **Không** |
| Chi phí tính toán ở máy chủ | Cao | Trung bình | **Thấp** |
| Rủi ro lộ diện người tham gia | Cao | Cao | Thấp hơn — **nhưng không phải ẩn danh** |

**Chọn: chuỗi điểm mốc bàn tay**, 126 chiều mỗi khung, lưu ở `.npz`.

Hai điều phải nói thẳng kèm lựa chọn này:

* **Đây là phép biến đổi có mất mát, và mất mát là một chiều.** Không lấy lại được
  video, nên cũng không trích lại được loại đặc trưng khác về sau. Nếu một nghiên
  cứu tương lai cần biểu cảm khuôn mặt, dữ liệu đã thu **không phục vụ được** —
  phải thu lại.
* **Không được lập luận "điểm mốc là ẩn danh".** Chuỗi điểm mốc không mang hình
  ảnh khuôn mặt, nhưng vẫn là dữ liệu về một con người cụ thể và vẫn quy về người
  đó được khi ghép với siêu dữ liệu khác. Thuật ngữ dùng thống nhất là **"không
  lộ diện"**, không phải "ẩn danh".

### 8.3.3 Tổ chức các bước xử lý

| Tiêu chí | Xử lý đồng bộ trong yêu cầu | Mỗi bước một tác vụ nền | **Gộp các bước vào một tác vụ nền** |
|---|---|---|---|
| Người dùng phải chờ | Có | Không | Không |
| Số lần chạm hàng đợi | 0 | Nhiều | 1 |
| Chạy lại từng bước riêng | — | Được | **Không** — chạy lại cả cụm |
| Trạng thái trung gian phải lưu | Không | Nhiều | **Ít** |
| Độ phức tạp vận hành | Thấp | **Cao** | Trung bình |

**Chọn: gộp các bước vào một tác vụ nền.** Đánh đổi được chấp nhận có ý thức: mất
khả năng chạy lại từng bước riêng, đổi lấy việc không phải quản lý một chuỗi
trạng thái trung gian. Với quy mô một máy chủ, một hàng đợi, chi phí vận hành của
phương án giữa lớn hơn giá trị nó mang lại.

**Giới hạn phải ghi:** vì cả cụm chạy lại cùng nhau, tính lũy đẳng phải bảo đảm ở
mức cụm. Hiện **chưa bảo đảm đồng đều**: bước ghi tệp đặc trưng chạy lại an toàn,
nhưng bước tải lên kho ngoài có thể tạo bản trùng.

### 8.3.4 Thẩm quyền ký trong cơ chế nguồn sự thật

| Tiêu chí | Không ký, tin vào kho lưu trữ | Mọi máy đều ký được | **Một máy phát hành duy nhất giữ khoá ký** |
|---|---|---|---|
| Phát hiện sửa đổi | Không | Có | **Có** |
| Xác định được ai sửa | Không | Có | **Có** |
| Rủi ro khoá bị lộ | — | **n lần** | 1 lần |
| Hợp nhất hai máy | Ghi đè lẫn nhau | Xung đột | **Một chiều, chỉ điền** |
| Chi phí vận hành | Thấp | Cao | Trung bình |

**Chọn: một máy phát hành duy nhất**, giữ khoá riêng Ed25519. Các máy khác chỉ
đọc: lúc khởi động kéo bản mới nhất, kiểm chữ ký với khoá công khai, rồi bảo đảm
cơ sở dữ liệu của mình là **tập cha** của bản đó — thêm cái thiếu, **không bao
giờ xoá**.

| Tính chất | Nghĩa | Trạng thái |
|---|---|---|
| **Toàn vẹn** | Sửa được nhưng không giấu được | **Đạt** — bản kê SHA-256, chữ ký phủ bản kê |
| **Xác thực nguồn** | Biết ai ký, không chỉ biết "có chữ ký hợp lệ" | **Đạt** — trả về tên khoá đã đăng ký |
| **Đơn điệu phiên bản** | Bản mới không bị bản cũ ghi đè lùi | **Chưa cưỡng chế** |

*Một bài học thiết kế:* danh sách cột bắt buộc dùng để kiểm bản công bố từng
**thiếu sáu cột**. Hệ quả: một bản công bố có lược đồ thiếu vẫn **qua được khâu
xác minh**, rồi mới hỏng giữa chừng lúc nhập dữ liệu. Đây là ví dụ điển hình của
"phép kiểm không phủ hết thứ mà nó bảo vệ", và là lý do phép đo phải chạy qua
**đúng đường tiêu thụ của ứng dụng**, không qua hàm trợ giúp.

---

## 8.4 Đóng góp kiến trúc lõi — Bốn tầng cưỡng chế cách ly

Bốn tầng, mỗi tầng bịt **một lối vòng** mà ba tầng còn lại để hở.

| Tầng | Cơ chế | Lối vòng nó bịt |
|:--:|---|---|
| **1** | **Cột phân biệt** — mỗi bảng chịu ranh giới tổ chức mang một cột định danh tổ chức | Không bịt gì cả. Một mình nó **chỉ là siêu dữ liệu**: không có gì buộc truy vấn phải dùng nó |
| **2** | **Chính sách bảo mật mức hàng** — so cột phân biệt với một biến ngữ cảnh của phiên | Truy vấn quên điều kiện lọc |
| **3** | **Phạm vi giao dịch** — biến ngữ cảnh gán bằng lệnh giới hạn trong giao dịch, trong một khối duy nhất | Rò ngữ cảnh sang yêu cầu kế tiếp qua bể kết nối |
| **4** | **Tách vai cơ sở dữ liệu** — vai chạy chỉ có quyền thao tác dữ liệu, không có quyền DDL, không phải siêu người dùng | Ứng dụng **tự tắt** chính sách |

### Tầng 2 — chi tiết quyết định nằm ở dạng đọc biến

Hàm đọc biến ngữ cảnh được gọi ở dạng **"cho phép thiếu"**, nên khi biến chưa
được gán, phép so sánh cho ra `NULL`. **`NULL` không phải `TRUE`**, nên hàng không
lọt qua chính sách. Đó chính là cơ chế làm mệnh đề *"không khai báo tổ chức ⇒ 0
hàng"* thành đúng.

Nếu dùng dạng đọc "bắt buộc có", biến chưa gán sẽ **ném lỗi** — nghe có vẻ an
toàn hơn, nhưng thực tế biến mọi công việc nền hợp lệ thành lỗi hệ thống, và áp
lực vận hành sẽ đẩy người ta tới chỗ **tắt chính sách**. Fail-closed *im lặng* ở
đây an toàn hơn fail-closed *ồn ào*.

### Tầng 3 — vì sao phải giới hạn trong giao dịch

Lệnh gán thường (không giới hạn giao dịch) sẽ **dính lại trên kết nối** và rò
sang yêu cầu kế tiếp khi dùng bể kết nối. Đây là lỗi kinh điển của cặp *bảo mật
mức hàng + bể kết nối*, và nó **không sinh ra thông báo lỗi nào** — chỉ có một
người dùng xui xẻo đọc được dữ liệu của người khác.

### Tầng 4 — vì sao cờ cưỡng chế vẫn chưa đủ

Cơ sở dữ liệu miễn trừ chính sách **vô điều kiện** cho vai siêu người dùng. Bật cờ
"cưỡng chế cả với chủ sở hữu bảng" không giải quyết được điều đó. Vai chạy của ứng
dụng vì thế không được là siêu người dùng, và điều đó phải **kiểm được bằng truy
vấn siêu dữ liệu** chứ không bằng niềm tin.

### Biến ngữ cảnh thứ hai

Phục vụ công việc nền hợp lệ xuyên tổ chức: đối soát lúc khởi động, tiến trình đọc
nguồn sự thật, bảo trì theo lịch. Nó là **một biến riêng biệt**, cố ý, chứ không
phải một "giá trị tổ chức đặc biệt" — nếu "hành động thay mọi tổ chức" là một giá
trị của cùng biến tổ chức thì một lỗi gõ sai tên tổ chức có thể vô tình sinh ra
đặc quyền đó.

---

## 8.5 Tương tác giữa các thành phần

Lấy nghiệp vụ trục chính — **thu một mẫu qua webcam** — làm ví dụ, vì nó chạm vào
gần như mọi thành phần:

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
2, thứ đi qua mạng là một mảng số vài chục KiB thay vì một tệp video vài MiB. Hệ
quả dây chuyền: băng thông thấp hơn, kho lưu trữ nhỏ hơn, và **không có video thô
để rò rỉ**.

**Bước 6 trả về trước khi bước 7–12 xảy ra.** Người dùng không chờ. Đổi lại, giao
diện phải có đường hỏi trạng thái (bước 13) và phải xử lý được trạng thái "đang xử
lý" như một trạng thái hợp lệ chứ không phải một lỗi.

**Bước 8 xảy ra trước bước 9.** Bản thô được ghi **trước** mọi bước chuẩn hoá.
Nếu bước chuẩn hoá có lỗi, dữ liệu gốc vẫn còn để xử lý lại. Thứ tự này là một
ràng buộc thiết kế, không phải một chi tiết cài đặt.

---

## 8.6 Luồng xử lý bất đồng bộ

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

**Bốn nhóm công việc chạy nền:** trích đặc trưng và chuẩn hoá · đồng bộ kho lưu
trữ ngoài · dựng bản xem trước · bảo trì theo lịch (đối soát, nhắc hạn, sao lưu,
dọn dẹp).

**Hai chỉ số chất lượng, và khả năng tái lập của chúng khác nhau.** Độ đầy đủ tính
lại được từ tệp đặc trưng; **độ rung thì không**, vì nó phụ thuộc chuỗi thời gian
trước khi chuẩn hoá. Một chỉ số tái lập được và một chỉ số không tái lập được
**không có cùng giá trị chứng minh**. Ngoài ra, **độ đầy đủ bằng 0 không có nghĩa
tệp rỗng** — nó có nghĩa không phát hiện được bàn tay nào, và hai điều đó khác
nhau.

---

## 8.7 Cơ chế nguồn sự thật ký số

**Luồng công bố** (chỉ trên máy phát hành):

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

Ba điểm DỪNG này là lý do `sot-init` có thể chặn toàn bộ hệ thống khởi động.

---

## 8.8 Kiến trúc quan trắc

**Ba tầng:** chỉ số (Prometheus) → biểu đồ và cảnh báo (Grafana) → nhật ký (Loki +
Promtail).

**Cảnh báo sống ở Grafana**, không có thành phần quản lý cảnh báo riêng — quyết
định hợp với quy mô một máy chủ.

Hai bài học vận hành đã trả giá:

* **Nhãn phân loại nhật ký phải ít.** Đặt định danh tổ chức làm nhãn sinh ra số
  chuỗi nhật ký bằng *số tổ chức × số dịch vụ*, và làm hệ thống nhật ký sập.
  Thông tin phân biệt phải nằm ở **siêu dữ liệu có cấu trúc**.
* **Giá trị đặc biệt để tránh suy luận sai.** Chỉ số trả về `-1` nghĩa là *"không
  đo được"*, khác hẳn `0` nghĩa là *"đo được và bằng không"*. Không phân biệt hai
  giá trị này thì biểu đồ vẽ một đường bằng phẳng ở đáy và **không ai biết hệ
  thống đang mù**.

**Nhật ký kiểm toán ghi ở hai nơi:** Redis (đường nhanh, đọc trong ứng dụng) và
`audit_log` trong PostgreSQL (bản bền). Ghi **fail-closed** khi không có phạm vi.

---

## 8.9 Năm nguyên lý thiết kế xuyên suốt

1. **Thiếu ngữ cảnh thì dừng, không đoán.** Áp cho cách ly (không có tổ chức ⇒ 0
   hàng), danh mục (thiếu dữ liệu ⇒ dừng), nguồn sự thật (không xác minh được ⇒
   không khởi động), nhật ký kiểm toán (không có phạm vi ⇒ từ chối ghi).
2. **Kế thừa lúc khởi tạo khác với rơi về lúc chạy.** Hai thứ trông giống nhau
   trên sơ đồ nhưng khác nhau hoàn toàn về hệ quả.
3. **Ngoại lệ phải là một phạm vi, không phải một lối đi vòng.**
4. **Tổng hợp cũng có thể rò rỉ.**
5. **Không có đường quay ngược từ công khai vào riêng tư.** Vì thế đường công bố
   phải là hành động tường minh, có xác thực lại, và có bản ghi.

---

## 8.10 Ba giới hạn thiết kế, nêu tại chỗ

1. **Hai cấp phạm vi dưới (không gian làm việc, dự án) chưa có bề mặt vận hành.**
   Có bảng, có `scope_level`, nhưng 0 bản ghi gán vai và không đường dẫn API nào.
2. **Tính lũy đẳng chưa đồng đều ở đường xử lý nền.** Tải đối tượng lên kho ngoài
   có thể tạo bản trùng khi chạy lại.
3. **Đơn điệu phiên bản của nguồn sự thật chưa được cưỡng chế.** Bản công bố cũ
   hơn vẫn được chấp nhận; tài nguyên mới không bị xoá nhưng giá trị dùng chung bị
   ghi đè lùi.
