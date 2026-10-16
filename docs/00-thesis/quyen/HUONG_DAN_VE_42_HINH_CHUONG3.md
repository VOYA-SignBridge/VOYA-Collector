# ĐẶC TẢ 42 HÌNH CHƯƠNG 3 — TÀI LIỆU ĐỂ VẼ

> **Cách dùng.** Mỗi hình có bốn phần bắt buộc: **Loại & công cụ** · **Phải thể
> hiện** (danh sách phần tử, không thiếu không thừa) · **Điểm phải nhìn thấy được**
> (thứ mà nếu hình không truyền đạt được thì hình vô dụng) · **Chú thích**. Khi nhờ
> người khác vẽ, đưa nguyên mục của hình đó.
>
> **Mốc dữ liệu.** Mọi con số trong tài liệu này đo trên `signdb` đang chạy ngày
> **18/08/2026**, lược đồ phiên bản 5. Nếu vẽ sau khi lược đồ đổi thì phải đếm lại.

---

## 0. Quy ước chung — đọc trước khi vẽ hình đầu tiên

### 0.1 Chuẩn, công cụ và loại sơ đồ

Toàn bộ hình theo **UML 2.5.1** với các sơ đồ UML, và **Crow's Foot** với các mô
hình dữ liệu. Công cụ đề xuất: **draw.io** cho sơ đồ tự do và infographic,
**PlantUML** cho use case / sequence / activity / state, **PowerDesigner** cho
CDM / LDM / PDM.

*Bảng 0-1: Bảy loại hình dùng trong chương và số lượng*

| Loại hình | Dùng cho | Các hình |
|---|---|:--|
| Sơ đồ ngữ cảnh | Ranh giới hệ thống và bên ngoài | 3.1, 3.2 |
| Sơ đồ kiến trúc / khối | Thành phần và quan hệ giữa chúng | 3.3, 3.19, 3.20, 3.40, 3.42 |
| Infographic | Truyền đạt một cấu trúc khái niệm | 3.5, 3.9, 3.11, 3.18, 3.34 |
| Use case diagram | Tác nhân × chức năng | 3.6, 3.7, 3.8, 3.10, 3.12, 3.15 |
| Activity diagram | Diễn tiến xử lý | 3.4, 3.17, 3.21, 3.33, 3.39, 3.41 |
| Sequence diagram | Trao đổi thông điệp theo thời gian | 3.13, 3.14, 3.32, 3.35, 3.36 |
| State machine | Vòng đời một đối tượng | 3.37 |
| Mô hình dữ liệu | CDM / LDM / PDM | 3.16, 3.22–3.31, 3.38 |

### 0.2 Quy ước trắng đen — **bắt buộc**

Hình in trong quyển là **trắng đen**. **Không dùng màu** để phân biệt bất cứ thứ gì.
Phân biệt chỉ bằng **hình dạng**, **kiểu nét** và **nhãn chữ**.

*Bảng 0-2: Cách phân biệt trong bản in trắng đen*

| Cần phân biệt | Cách ĐÚNG | Cách SAI |
|---|---|---|
| Luồng chính vs luồng ngoại lệ | nét liền vs **nét đứt** | đen vs đỏ |
| Tác nhân người vs tác nhân hệ thống | người que vs **hình chữ nhật `«system»`** | xanh vs xám |
| **Đã hiện thực vs thiết kế đích** | nét liền vs **nét đứt + nhãn `«target design»`** | mờ vs đậm |
| Hành động tự động của hệ thống | khuôn chữ `«internal»` | tô nền |
| Vùng trách nhiệm | **phân làn** có tên | nền khác nhau |
| Ranh giới cưỡng chế được vs không | nét **đậm liền** vs nét **mảnh chấm** | hai màu |

Với PlantUML, giữ nguyên `skinparam monochrome true` trong mọi mã nguồn.

### 0.3 Ba trạng thái hiện thực — ký hiệu thống nhất

Đây là quy ước quan trọng nhất của cả tài liệu. Chương 3 trình bày cả phần đã chạy
lẫn phần mới ở mức thiết kế, và **hình không được phép làm hai thứ đó trông giống
nhau**.

| Ký hiệu trên hình | Nghĩa | Vẽ bằng |
|:--:|---|---|
| **✔** | Đã hiện thực, kiểm chứng được từ bên ngoài | nét liền |
| **◐** | Một phần — có bề mặt nhưng cưỡng chế chưa đầy đủ | nét liền + nhãn `«partial»` |
| **○** | Thiết kế đích — chưa có bảng hoặc chưa có bề mặt | **nét đứt** + nhãn `«target design»` |

Ba nhóm phải mang ký hiệu này ở mọi hình chúng xuất hiện:

* **Workspace / Project** → **◐** (có bảng, có 14 điểm cuối API, nhưng dữ liệu chưa
  mang định danh dự án và chế độ phân quyền đang ở `shadow`).
* **Dataset / DatasetVersion / SampleRevision** → **○** (không có bảng nào trong số
  này trên cơ sở dữ liệu đang chạy).
* **Community Data Commons** → **○** (tenant dự trữ đã có, dữ liệu chưa có).

### 0.4 Bốn thuật ngữ hay bị vẽ sai

1. **Community ≠ danh mục hệ thống.** Ba bảng `community_*` là **danh mục hệ thống**
   (cấu hình phương ngữ và hồ sơ nhận dạng); tên bảng là di sản. **Community là một
   hàng của bảng `tenants`** với `tenant_type='COMMUNITY'`. Vẽ Community thành một
   mặt phẳng ngoài cây tổ chức là **sai**, vì nó gợi ý một đường đọc không chịu cách ly.
2. **`default` không phải dữ liệu chung.** Là một tổ chức bình thường, đang giữ
   corpus thật (3.860 mẫu / 63 lớp).
3. **Người ký ≠ tài khoản vận hành.** Hai vai khác nhau, hai cạnh khác nhau trên hình.
4. **Ghim phiên bản danh mục ≠ ghim nội dung bộ dữ liệu.** Hệ thống chỉ làm vế thứ nhất.

### 0.5 Luật vòng lặp

**Mọi vòng lặp phải có bộ đếm, giới hạn ghi bằng số, và nhánh thoát dẫn tới nút kết
thúc.** Ba vòng lặp có thật trong hệ thống:

| Vòng lặp | Giới hạn | Hết lượt thì đi đâu |
|---|---|---|
| Nhập sai mật khẩu | 10 lần, rồi khoá theo bậc 30s → 120s → 300s → **900s và dừng** | Màn hình báo thời gian chờ |
| Nhập sai mã xác thực | hết ngân sách lần thử của mã | Mã bị vô hiệu, phải xin mã mới |
| Đẩy tệp lên kho ngoài | **5 lần, cách nhau 10 giây** | Giữ đường dẫn cục bộ; tác vụ đối soát vá sau |

---

# PHẦN A — NGỮ CẢNH VÀ TỔNG QUAN (Hình 3.1 – 3.5)

## HÌNH 3.1 — Bối cảnh bài toán thu thập dữ liệu VSL đa tổ chức

**Loại & công cụ:** sơ đồ ngữ cảnh · draw.io

**Phải thể hiện:**
* **Ba tổ chức độc lập** vẽ thành ba khối, mỗi khối có **đường viền đậm liền** đánh
  dấu ranh giới dữ liệu. Ba khối **không chồng lấn và không có mũi tên nối ngang**.
* Trong mỗi khối, bốn nhóm tài nguyên xếp theo thứ tự nghiệp vụ:
  `Danh mục từ vựng` → `Người ký` → `Phiên thu` → `Mẫu dữ liệu`.
* Một khối lớn bao ba khối đó, ghi **CTU.SignBridge — phân hệ thu thập và quản lý
  dữ liệu**.
* Bên **ngoài** khối lớn: `Nghiên cứu hạ nguồn` và `Nhận dạng thời gian thực`, vẽ
  bằng **nét đứt** với nhãn `«downstream»`.
* Một mũi tên duy nhất từ khối lớn ra hai khối hạ nguồn, nhãn *"dữ liệu đã quản lý,
  qua cổng đồng thuận"*.

**Điểm phải nhìn thấy được:** ba tổ chức dùng **chung một hạ tầng** nhưng **không có
đường nối nào giữa ba khối dữ liệu**. Nếu người đọc nhìn hình mà vẫn nghĩ dữ liệu có
thể chảy ngang, hình đã hỏng.

**Không được vẽ:** một khối "dữ liệu dùng chung" nằm giữa ba tổ chức.

**Chú thích:** *Hình 3.1: Bối cảnh bài toán — nhiều tổ chức đóng góp dữ liệu VSL
trong các ranh giới dữ liệu tách biệt.*

---

## HÌNH 3.2 — Ngữ cảnh của phân hệ thu thập và quản lý dữ liệu VSL

**Loại & công cụ:** sơ đồ ngữ cảnh hai lớp · draw.io

**Phải thể hiện:**
* **Lớp trong cùng** — *Phân hệ thu thập và quản lý dữ liệu VSL* (đối tượng nghiên
  cứu của luận văn), chứa sáu phân hệ: Danh tính & Phiên · Tổ chức & Phân quyền ·
  Danh mục VSL · Thu nhận & Xử lý · Bộ dữ liệu & Quản trị dữ liệu · Toàn vẹn & Vận hành.
* **Lớp giữa** — ranh giới *CTU.SignBridge*. Giữa hai lớp đặt **Huấn luyện** và
  **Nhận dạng thời gian thực**, nhãn `«downstream consumer»`, **nét đứt**.
* **Lớp ngoài** — bốn tác nhân ngoài hệ thống, mỗi tác nhân ghi rõ chiều mũi tên:

| Tác nhân ngoài | Chiều | Nhãn trên mũi tên |
|---|---|---|
| Người dùng (khách, thành viên, biên tập viên, quản trị) | vào | HTTPS |
| Dịch vụ gửi tin (SMTP + SMS) | **ra** | mã xác thực, lời mời, cảnh báo |
| Kho lưu trữ ngoài (Drive + Sheets) | **ra** | bản sao — **không bao giờ là bản gốc** |
| Máy phát hành tạo tác đã ký | **vào, một chiều** | hệ thống **kéo** rồi tự xác minh |

**Điểm phải nhìn thấy được:** máy phát hành **không gọi vào** hệ thống — hệ thống kéo
tạo tác về và tự xác minh chữ ký. Vẽ ngược chiều là mô tả sai mô hình tin cậy.

**Chú thích:** *Hình 3.2: Ngữ cảnh phân hệ nghiên cứu trong ranh giới CTU.SignBridge.*

---

## HÌNH 3.3 — Kiến trúc giải pháp mức cao

**Loại & công cụ:** sơ đồ khối phân tầng · draw.io

**Phải thể hiện — bốn nhánh, vẽ tách bạch:**

```
NHÁNH 1 — đường đồng bộ
  Người dùng → Trình duyệt → Cổng vào (reverse proxy) → Dịch vụ ứng dụng → PostgreSQL

  Dịch vụ ứng dụng chứa SÁU khối con, xếp dọc:
     Danh tính & Phiên
     Tổ chức & Phân quyền
     Danh mục & Registry
     Thu nhận & Quản lý mẫu
     Đồng thuận & Quản trị dữ liệu
     Kiểm toán & Quản trị nền tảng

NHÁNH 2 — đường bất đồng bộ
  Dịch vụ ứng dụng → Hàng đợi Redis → Tiến trình nền → Kho tệp đặc trưng & tạo tác

NHÁNH 3 — đường ra ngoài
  Dịch vụ ứng dụng → Kho lưu trữ ngoài (bản sao)
  Dịch vụ ứng dụng → Dịch vụ gửi tin

NHÁNH 4 — đường hạ nguồn
  Dữ liệu đã quản lý → Huấn luyện / Nhận dạng      «downstream», nét đứt
```

* Ba thành phần **nằm ngoài** đường viền ứng dụng: dịch vụ gửi tin, kho lưu trữ
  ngoài, máy phát hành tạo tác đã ký.
* Ranh giới đồng bộ / bất đồng bộ vẽ bằng **một đường kẻ ngang có nhãn**.

**Không được vẽ:** toàn bộ 15 container triển khai. Đây là hình kiến trúc **luận
lý**; container thuộc Hình 3.42.

**Chú thích:** *Hình 3.3: Kiến trúc giải pháp mức cao.*

---

## HÌNH 3.4 — Quy trình vận hành tổng quát

**Loại & công cụ:** activity diagram · PlantUML

**Phải thể hiện — mười một bước, có ba nhánh rẽ:**

```
● bắt đầu
↓ Xác thực người dùng
↓ Phân giải tổ chức và quyền
◇ [thiếu quyền] ──→ Từ chối, ghi kiểm toán ──→ ⊗
↓ [đủ quyền]
↓ Chọn lớp từ vựng
↓ Chọn người ký và phiên thu
◇ [chưa có đồng thuận người ký] ──→ Điều hướng màn hình đồng thuận ──→ ⊗
↓ [có đồng thuận]
▬ fork
   ├─ Thu qua camera   (trích điểm mốc TẠI MÁY KHÁCH)
   └─ Tải lên tệp video (ghi bản thô TRƯỚC chuẩn hoá)
▬ join
↓ Kiểm tra hợp lệ
↓ Xử lý nền
◇ [không phát hiện được bàn tay] ──→ Tác vụ thất bại, KHÔNG tạo mẫu ──→ ⊗
↓ [đạt]
▯ Mẫu đã quản lý          ← object node
↓ Rà soát và quản trị dữ liệu
↓ Xuất dữ liệu hoặc dùng ở hạ nguồn
◉ kết thúc
```

**Điểm phải nhìn thấy được:** cổng đồng thuận đứng **trước** bước thu, không phải sau.
Đây là hệ quả của việc đồng thuận gắn với **người ký** chứ không với tài khoản.

**Chú thích:** *Hình 3.4: Quy trình vận hành tổng quát của phân hệ.*

---

## HÌNH 3.5 — Bản đồ năng lực chức năng

**Loại & công cụ:** infographic · draw.io

**Phải thể hiện:**
* **Tâm:** khối `DỮ LIỆU VSL ĐÃ QUẢN LÝ`, vẽ đậm nhất.
* **Tám nhóm chức năng** xếp vòng quanh, mỗi nhóm ghi mã nghiệp vụ và số use case:

| Vị trí | Nhóm | Mã | Kiểu vẽ |
|---|---|---|---|
| 12 h | Danh tính và quyền truy cập | NV1 · 14 UC | nét liền |
| 1 h 30 | Thu thập và quản lý dữ liệu mẫu | NV2 · 13 UC | nét liền **đậm** |
| 3 h | Danh mục từ vựng và phương ngữ | NV3 · 10 UC | nét liền **đậm** |
| 4 h 30 | Huấn luyện, đánh giá và suy luận | NV4 · 9 UC | **nét đứt** `«downstream»` |
| 6 h | Tổ chức và đăng ký dịch vụ | NV5 · 8 UC | nét liền **đậm** |
| 7 h 30 | Quản trị người dùng và chính sách | NV6 · 9 UC | nét liền |
| 9 h | Vận hành và nguồn sự thật | NV7 · 6 UC | nét liền |
| 10 h 30 | Hỗ trợ và tích hợp | NV8 · 6 UC | **nét đứt** `«vành ngoài»` |

* Bốn nhóm **nét liền đậm** (NV2, NV3, NV5 và một phần NV1) là phần mang đóng góp
  của luận văn.

**Điểm phải nhìn thấy được:** huấn luyện và nhận dạng **không đứng ngang hàng** với
các nhóm còn lại. Nếu chúng trông ngang hàng, hội đồng sẽ hỏi *"đề tài là quản lý dữ
liệu hay huấn luyện?"*.

**Chú thích:** *Hình 3.5: Bản đồ năng lực chức năng quanh dữ liệu VSL đã quản lý.*

---

# PHẦN B — TÁC NHÂN VÀ USE CASE (Hình 3.6 – 3.15)

## HÌNH 3.6 — Sơ đồ tổng quát hoá tác nhân

**Loại & công cụ:** use case diagram (phần tác nhân) · PlantUML

**Phải thể hiện — ba nhánh kế thừa tách biệt:**

```
        Khách vãng lai                    (đứng riêng, không kế thừa ai)

        Người dùng đã đăng ký  «abstract»
                  ▲
                  │ kế thừa
        Thành viên tổ chức
                  ▲
        ┌─────────┼─────────────┐
   Người đóng góp  Biên tập viên  Quản trị tổ chức
     dữ liệu        dữ liệu

        Quản trị nền tảng                 (TÁCH HẲN, không nối vào nhánh trên)

        Người ký  «data subject»          (TÁCH HẲN, không phải người dùng phần mềm)
```

* Mũi tên kế thừa: **tam giác rỗng, nét liền**.
* `Người ký` vẽ bằng người que **có nhãn `«data subject»`** và **không có cung nào**
  nối tới nhóm người dùng.

**Điểm phải nhìn thấy được — hai ranh giới:**
1. **Quản trị nền tảng KHÔNG kế thừa Quản trị tổ chức** và ngược lại. Quản trị tổ
   chức kiểm bằng vai trong **một** tổ chức và đưa người vào bằng **lời mời**; quản
   trị nền tảng kiểm bằng cờ trên tài khoản, phạm vi toàn nền tảng.
2. **Người ký không nhất thiết là người dùng phần mềm.** Họ là chủ thể dữ liệu; đồng
   thuận gắn vào họ, không gắn vào tài khoản bấm nút thu.

**Chú thích:** *Hình 3.6: Sơ đồ tổng quát hoá tác nhân và hai ranh giới không được
vẽ sai.*

---

## HÌNH 3.7 — Use case: Quản lý danh tính và truy cập

**Loại & công cụ:** use case diagram · PlantUML

**Phải thể hiện:**
* Tác nhân: `Khách vãng lai`, `Người dùng đã đăng ký`; tác nhân phụ `Dịch vụ gửi tin
  «system»` đặt bên phải, **ngoài** khung hệ thống.
* Use case trong khung: Đăng ký tài khoản · Đăng ký theo lời mời · Đăng nhập · Xác
  thực yếu tố thứ hai · Đăng xuất · Khôi phục tài khoản · Quản lý bảo mật tài khoản ·
  Quản lý hồ sơ cá nhân · Xem văn bản pháp lý · **Chấp thuận văn bản pháp lý** · Gửi
  mã xác thực.
* Quan hệ:

| Từ | Loại | Tới | Điều kiện ghi trên cung |
|---|---|---|---|
| Đăng ký tài khoản | `«include»` | Chấp thuận văn bản pháp lý | — |
| Đăng ký theo lời mời | `«include»` | Gửi mã xác thực | — |
| Khôi phục tài khoản | `«include»` | Gửi mã xác thực | — |
| Xác thực địa chỉ liên hệ | `«include»` | Gửi mã xác thực | — |
| Xác thực yếu tố thứ hai | `«extend»` | Đăng nhập | *khi tài khoản bật 2FA* |

**Điểm phải nhìn thấy được:** quan hệ *Đăng ký* → *Chấp thuận văn bản pháp lý* là
`«include»` **chứ không phải** `«extend»`. Đây là một khẳng định thiết kế: **không
tồn tại tài khoản chưa chấp thuận**. Điều kiện này được cưỡng chế ở **cả hai tầng** —
giao diện vô hiệu nút tạo tài khoản, và cơ sở dữ liệu ghi bản ghi chấp thuận trong
cùng giao dịch với bản ghi tài khoản.

Ghi chú `«include»` từ ba use case khác nhau tới *Gửi mã xác thực* là lý do use case
đó tồn tại riêng thay vì là một bước trong ba luồng.

**Chú thích:** *Hình 3.7: Use case nhóm Quản lý danh tính và truy cập.*

---

## HÌNH 3.8 — Use case: Quản lý tổ chức và phân quyền

**Loại & công cụ:** use case diagram · PlantUML

**Phải thể hiện:**
* Tác nhân: `Quản trị tổ chức`, `Quản trị nền tảng`, `Khách vãng lai` (cho use case
  chấp nhận lời mời); tác nhân phụ `Dịch vụ gửi tin «system»`.
* Use case: Quản lý tổ chức ✔ · **Quản lý không gian làm việc ◐** · **Quản lý dự án ◐** ·
  Mời thành viên ✔ · Chấp nhận lời mời ✔ · Gỡ thành viên ✔ · **Quản lý gán vai theo
  phạm vi ◐** · Quản lý gói dịch vụ ✔ · Yêu cầu xuất dữ liệu tổ chức ✔ · Dọn sạch dữ
  liệu tổ chức ✔.
* Ba use case mang **◐** vẽ **nét liền kèm nhãn `«partial»`**, và có một ghi chú gấp
  góc nối vào: *"có bề mặt API; dữ liệu chưa phân vùng theo cấp này; quyết định quyền
  lúc chạy vẫn ở hệ hai phạm vi"*.
* Quan hệ `«extend»` từ `Xác thực lại thao tác nhạy cảm` tới **hai** use case: *Dọn
  sạch dữ liệu tổ chức* và *Công bố văn bản pháp lý* (use case thứ hai vẽ mờ ở rìa,
  chỉ để thể hiện cung).

**Điểm phải nhìn thấy được:** **không có cung nào** cho phép quản trị tổ chức thêm
thành viên trực tiếp theo mã tài khoản. Đường duy nhất là *Mời thành viên* → *Chấp
nhận lời mời*, và use case thứ hai do **chính người được mời** thực hiện.

**Chú thích:** *Hình 3.8: Use case nhóm Quản lý tổ chức và phân quyền.*

---

## HÌNH 3.9 — Phân cấp tổ chức và phân cấp phân quyền

**Loại & công cụ:** infographic hai cột · draw.io

**Phải thể hiện — hai cây đặt song song, có cầu nối:**

```
CỘT TRÁI — cây phạm vi              CỘT PHẢI — chuỗi phân quyền

  Hệ thống  ✔                        Người dùng
     │                                  │
     ▼                                  ▼
  Tổ chức  ✔  ◄══ RANH GIỚI DỮ       Tư cách thành viên   (mang cấp phạm vi)
     │           LIỆU ĐANG ĐƯỢC          │
     │           CƯỠNG CHẾ                ▼
     ▼                                Lần gán vai   (trỏ vào tư cách thành viên,
  Không gian làm việc  ◐                 │            KHÔNG trỏ vào cặp người–phạm vi)
     │                                  ▼
     ▼                                 Vai
  Dự án  ◐                              │
                                        ▼
                                      Quyền
```

* Ô `Tổ chức` vẽ **viền đậm nhất** kèm nhãn **"ranh giới dữ liệu đang được cưỡng chế"**.
* Hai ô dưới vẽ **nét liền + `«partial»`**, kèm ghi chú: *"36/36 bảng thuộc tổ chức
  mang cột định danh tổ chức; **0 bảng** mang định danh dự án"*.
* Vẽ một mũi tên **tự trỏ** ở ô `Tư cách thành viên`, nhãn *"cấp dưới phải có cấp
  trên — cưỡng chế bằng trigger"*.

**Điểm phải nhìn thấy được:** cây phạm vi có **bốn cấp**, nhưng **ranh giới dữ liệu
chỉ được cưỡng chế ở cấp Tổ chức**. Vẽ bốn cấp trông đều nhau là overclaim.

**Chú thích:** *Hình 3.9: Phân cấp tổ chức, chuỗi phân quyền, và cấp đang được cưỡng
chế làm ranh giới dữ liệu.*

---

## HÌNH 3.10 — Use case: Quản lý danh mục từ vựng VSL

**Loại & công cụ:** use case diagram · PlantUML

**Phải thể hiện:**
* Tác nhân: `Biên tập viên dữ liệu`, `Quản trị nền tảng`, `Thành viên tổ chức`.
* Use case: Duyệt danh mục lớp · **Đăng ký lớp ký hiệu** · Cập nhật lớp · Gộp hai lớp
  trùng · Gỡ lớp · Đề xuất phương ngữ · Kiểm duyệt đề xuất phương ngữ · **Mở rộng
  danh mục của tổ chức từ danh mục hệ thống** · Công bố phiên bản danh mục hệ thống ·
  Xem thống kê thu thập.
* Một ghi chú gấp góc nối vào *Mở rộng danh mục*: *"sao chép MỘT LẦN lúc khởi tạo tổ
  chức; lúc chạy KHÔNG có đường đọc ngược về danh mục hệ thống"*.

**Điểm phải nhìn thấy được:** *Đề xuất phương ngữ* (biên tập viên của tổ chức) và
*Kiểm duyệt đề xuất* (quản trị nền tảng) là **hai use case của hai tác nhân khác
nhau**. Một tổ chức không tự duyệt phương ngữ của mình vào danh mục dùng chung.

**Chú thích:** *Hình 3.10: Use case nhóm Quản lý danh mục từ vựng VSL.*

---

## HÌNH 3.11 — Infographic: Năm chiều định danh của một lớp ký hiệu

**Loại & công cụ:** infographic · draw.io

**Phải thể hiện:**
* **Tâm:** khối `LỚP KÝ HIỆU`.
* **Năm chiều** toả ra, mỗi chiều một ô, ghi cả tên cột thật:

| Chiều | Cột | Ví dụ |
|---|---|---|
| Tổ chức sở hữu | `tenant_id` | `default` |
| Nhãn chuẩn hoá | `slug` | `xin-chao` |
| Ngôn ngữ | `language` | `vsl` |
| Phương ngữ | `dialect` | `hoa-de` |
| **Vùng miền** | `region` | `can-tho` |

* Dưới hình đặt **hai ví dụ đối chứng**, vẽ thành hai khung cạnh nhau:

```
KHUNG 1 — HỢP LỆ, cả hai cùng tồn tại
  (default, xin-chao, vsl, hoa-de, can-tho)   ✔
  (default, xin-chao, vsl, hoa-de, ha-noi)    ✔   ← chỉ khác VÙNG MIỀN

KHUNG 2 — BỊ TỪ CHỐI
  (default, xin-chao, vsl, hoa-de, can-tho)   ✔
  (default, xin-chao, vsl, hoa-de, can-tho)   ✘   ← trùng cả năm chiều
```

**Điểm phải nhìn thấy được:** vùng miền là **một phần định danh**, không phải thuộc
tính mô tả. Hai biến thể cùng từ, cùng phương ngữ, khác vùng miền là **hai lớp khác
nhau** — vì chúng là hai ký hiệu khác nhau trong thực tế.

**Chú thích:** *Hình 3.11: Năm chiều định danh của một lớp ký hiệu, kèm đối chứng
hai chiều.*

---

## HÌNH 3.12 — Use case: Thu thập và quản lý dữ liệu mẫu VSL

**Loại & công cụ:** use case diagram · PlantUML

**Phải thể hiện:**
* Tác nhân chính: `Người đóng góp dữ liệu`, `Biên tập viên dữ liệu`.
* Tác nhân phụ, **ngoài** khung: `Kho lưu trữ ngoài «system»`.
* Use case: **Thu mẫu từ camera** · **Tải lên bản ghi có sẵn** · Theo dõi trạng thái
  xử lý · Duyệt danh mục lớp · Xem chi tiết lớp · Xem trước phiên thu · Xoá phiên thu ·
  Gán lại người ký · Xoá mẫu · Quản lý thùng rác · Quản lý người ký và đồng thuận ·
  Xem thống kê thu thập.
* Cung `«constraint»` **nét đứt** từ *Quản lý người ký và đồng thuận* tới *Thu mẫu từ
  camera*, nhãn *"thiếu đồng thuận ⇒ không thu được"*.

**Điểm phải nhìn thấy được — và đây là điểm quan trọng nhất của hình:** **hai đường
thu là hai use case tách bạch**, không phải hai nhánh của một use case:

```
Thu mẫu từ camera      : trích điểm mốc TẠI TRÌNH DUYỆT → gửi chuỗi số
                         ✗ video KHÔNG rời máy người dùng
Tải lên bản ghi có sẵn : ghi bản thô TRƯỚC → trích điểm mốc Ở MÁY CHỦ
```

**Không được vẽ:** *Tiến trình nền* / *Processing Worker* làm tác nhân. Nó là thành
phần **bên trong** ranh giới hệ thống; nó xuất hiện ở Hình 3.13, 3.14 và 3.36.

**Chú thích:** *Hình 3.12: Use case nhóm Thu thập và quản lý dữ liệu mẫu VSL.*

---

## HÌNH 3.13 — Sequence: Thu mẫu trực tiếp qua camera

**Loại & công cụ:** sequence diagram · PlantUML

**Sáu đường đời, theo đúng thứ tự trái sang phải:**
`Người đóng góp` · `Trình duyệt` · `Dịch vụ ứng dụng` · `PostgreSQL` · `Hàng đợi` ·
`Tiến trình nền`

**Trình tự thông điệp:**

```
 1  Người đóng góp → Trình duyệt : chọn lớp, người ký, phiên thu
 2  Trình duyệt                  : trích điểm mốc bằng WebAssembly   «local»
 3  Trình duyệt → Dịch vụ        : gửi chuỗi điểm mốc + siêu dữ liệu
 4  Dịch vụ → PostgreSQL         : MỞ PHẠM VI TỔ CHỨC (SET LOCAL)     ← khung ref
 5  Dịch vụ → PostgreSQL         : kiểm đồng thuận người ký
 6  Dịch vụ → PostgreSQL         : kiểm hạn mức tổ chức
 7  Dịch vụ → PostgreSQL         : ghi bản ghi mẫu, trạng thái chờ xử lý
 8  Dịch vụ → Hàng đợi           : đẩy tác vụ
 9  Dịch vụ → Trình duyệt        : trả mã tác vụ
    ╌╌╌╌╌ RANH GIỚI ĐỒNG BỘ / BẤT ĐỒNG BỘ ╌╌╌╌╌
10  Hàng đợi → Tiến trình nền    : lấy việc
11  Tiến trình nền               : cắt cửa sổ, tăng cường, chấm chất lượng
12  Tiến trình nền → PostgreSQL  : ghi tệp đặc trưng, cập nhật trạng thái sẵn sàng
13  Trình duyệt → Dịch vụ        : hỏi trạng thái   (loop, có giới hạn)
```

**Ba điểm phải đánh dấu nổi bật:**
1. Bước 2 mang nhãn `«local»` — **không có thông điệp nào mang video**.
2. Bước 4 vẽ trong **khung `ref`** để nhấn rằng đây là một khối quản lý ngữ cảnh duy
   nhất của mã nguồn.
3. Ranh giới đồng bộ / bất đồng bộ vẽ bằng đường kẻ ngang có nhãn.

**Nhánh ngoại lệ (vẽ bằng khung `alt`, nét đứt):** mất mạng ở bước 3 → dữ liệu điểm
mốc **giữ lại ở bộ nhớ trình duyệt** và gửi lại được; **không có bản ghi nào ở máy chủ**.

**Chú thích:** *Hình 3.13: Trình tự thu mẫu trực tiếp qua camera.*

---

## HÌNH 3.14 — Sequence: Xử lý bản ghi có sẵn

**Loại & công cụ:** sequence diagram · PlantUML

**Bảy đường đời:** `Người đóng góp` · `Trình duyệt` · `Dịch vụ ứng dụng` ·
`Kho tệp thô` · `PostgreSQL` · `Hàng đợi` · `Tiến trình nền`

**Trình tự:**

```
 1  chọn lớp, phương ngữ, người ký cho CẢ LÔ
 2  chọn tệp video, gửi kèm mã lô ổn định do máy khách sinh
 3  Dịch vụ : kiểm định dạng, dung lượng, thời lượng từng tệp
 4  Dịch vụ → PostgreSQL : kiểm hạn mức theo số tệp còn lại
 5  Dịch vụ → Kho tệp thô : GHI BẢN THÔ           ← TRƯỚC mọi bước chuẩn hoá
 6  Dịch vụ → PostgreSQL : ghi bản ghi bản tải lên thô
 7  Dịch vụ → Trình duyệt : biên nhận, liệt kê tệp nhận và tệp từ chối
 8  Dịch vụ → Hàng đợi : một tác vụ cho mỗi tệp
    ╌╌╌╌╌ RANH GIỚI ĐỒNG BỘ / BẤT ĐỒNG BỘ ╌╌╌╌╌
 9  Tiến trình nền : TRÍCH ĐIỂM MỐC Ở MÁY CHỦ     ← khác hẳn Hình 3.13
10  Tiến trình nền : chuẩn hoá, chấm chất lượng
11  Tiến trình nền → PostgreSQL : ghi mẫu, trạng thái sẵn sàng
```

**Điểm phải nhìn thấy được:** đặt cạnh Hình 3.13, hai hình phải cho thấy ngay **bước
trích điểm mốc nằm ở hai chỗ khác nhau**. Với đường camera, video chưa từng tồn tại ở
phía máy chủ nên **không có gì để trích lại**; với đường tệp, bản thô được giữ nên
**xử lý lại được**.

**Nhánh ngoại lệ:** một tệp sai định dạng → **các tệp còn lại trong lô vẫn được xử lý**.

**Chú thích:** *Hình 3.14: Trình tự xử lý bản ghi video có sẵn.*

---

## HÌNH 3.15 — Use case: Quản trị dữ liệu và toàn vẹn

**Loại & công cụ:** use case diagram · PlantUML

**Phải thể hiện:**
* Tác nhân: `Biên tập viên dữ liệu`, `Quản trị tổ chức`, `Quản trị nền tảng`,
  `Người ký «data subject»`; tác nhân phụ `Máy phát hành tạo tác đã ký «system»`.
* Use case: **Quản lý bộ dữ liệu ○** · **Tạo phiên bản bộ dữ liệu ○** · **Xem nguồn
  gốc ◐** · Xuất bộ dữ liệu ✔ · Cho và rút đồng thuận người ký ✔ · Công bố văn bản
  pháp lý ✔ · **Xác minh toàn vẹn nguồn sự thật ✔** · Đối soát nguồn sự thật và bản
  sao ✔ · Xem nhật ký kiểm toán theo phạm vi ✔.
* Ba use case **○** vẽ **nét đứt** kèm nhãn `«target design»` và một ghi chú: *"bốn
  bảng cần thiết không tồn tại trên cơ sở dữ liệu đang chạy"*.
* Cung `«constraint»` nét đứt từ *Cho và rút đồng thuận người ký* tới *Xuất bộ dữ liệu*.

**Điểm phải nhìn thấy được:** *Xem nhật ký kiểm toán* có **hai tác nhân** (quản trị
tổ chức và quản trị nền tảng) với **hai phạm vi khác nhau**, nhưng là **một use case**.
Và nó là use case **độc lập** — các use case quản trị khác **ghi** bản ghi kiểm toán
như hậu điều kiện, **không** `«include»` use case này.

**Chú thích:** *Hình 3.15: Use case nhóm Quản trị dữ liệu và toàn vẹn.*

---

# PHẦN C — MÔ HÌNH NGUỒN GỐC, ĐỘ TIN CẬY VÀ AN TOÀN (Hình 3.16 – 3.21)

## HÌNH 3.16 — Mô hình nguồn gốc hiện tại và mô hình phiên bản bộ dữ liệu đích

**Loại & công cụ:** sơ đồ quan hệ thực thể hai vùng · draw.io

**Phải thể hiện — hai vùng, phân cách bằng một đường kẻ dọc có nhãn:**

```
VÙNG TRÁI — ĐÃ HIỆN THỰC (nét LIỀN)          │ VÙNG PHẢI — THIẾT KẾ ĐÍCH (nét ĐỨT)
                                             │
  Người ký ──< Phiên thu ──< Mẫu             │   Bộ dữ liệu  ○
                              │              │      │
                              ├──< Bản tải   │      ▼
                              │    lên thô   │   Phiên bản bộ dữ liệu  ○
                              │              │      │
  Đồng thuận người ký ──chi phối──┘          │      ├──< Thành viên phiên bản  ○
                                             │      │
  Tác vụ huấn luyện ──ghim──> Phiên bản      │      └──> Bản sửa của mẫu  ○
                              danh mục       │
                              (KHÔNG GIAN    │
                               NHÃN)         │
```

* Quan hệ `Mẫu ─ Bản tải lên thô` vẽ **nét chấm mảnh** kèm nhãn *"không có khoá ngoại
  — chỉ qua cột kiểu nguồn và quy ước đặt tên"*.
* Ô `Phiên bản danh mục` ghi thêm: *"bất biến theo QUY ƯỚC ứng dụng, không có trigger"*.
* Bốn ô vùng phải ghi rõ: *"không tồn tại trên cơ sở dữ liệu đang chạy"*.

**Điểm phải nhìn thấy được:** hệ thống ghim được **không gian nhãn**, **chưa ghim
được nội dung bộ dữ liệu**. Toàn bộ lập luận về khả năng tái lập của luận văn dừng
đúng ở đường kẻ dọc giữa hai vùng.

**Không được vẽ:** quan hệ `Phiên bản bộ dữ liệu → Bản sửa của mẫu` bằng nét liền.
Vẽ nét liền là bịa lược đồ, và người phản biện kiểm được bằng một câu lệnh mô tả bảng.

**Chú thích:** *Hình 3.16: Mô hình nguồn gốc đã hiện thực (nét liền) và mô hình phiên
bản bộ dữ liệu ở mức thiết kế đích (nét đứt).*

---

## HÌNH 3.17 — Xử lý bất đồng bộ tin cậy và cơ chế khôi phục

**Loại & công cụ:** activity diagram có phân làn · PlantUML

**Ba làn:** `Dịch vụ ứng dụng` · `Hàng đợi` · `Tiến trình nền`

**Phải thể hiện:**

```
LÀN 1 — Dịch vụ ứng dụng
  ● → Ghi bản ghi mẫu (chờ xử lý) → Đẩy tác vụ → Trả mã tác vụ → ⊗

LÀN 2 — Hàng đợi
  Giữ tác vụ → cấp cho tiến trình nền

LÀN 3 — Tiến trình nền
  Nhận việc, đánh dấu đang chạy
  ↓ GHI KHO THÔ                    ← TRƯỚC mọi bước chuẩn hoá
  ↓ Cắt cửa sổ, chuẩn hoá
  ◇ [không phát hiện được bàn tay] → Kết thúc thất bại, KHÔNG tạo mẫu → ◉
  ↓ [đạt]
  ◇ [cửa sổ ngắn hơn quy định] → Đệm thêm VÀ ghi vào chỉ số chất lượng → (nhập lại)
  ↓ Chấm chất lượng → Ghi tệp đặc trưng + tệp mô tả đi kèm
  ↓ Nối dòng vào nguồn sự thật
  ◇ [ghi nguồn sự thật thất bại] → Huỷ, xếp hàng lại → (về đầu làn 3)
  ↓ [đạt] Phản chiếu sang cơ sở dữ liệu
  ↓ Đẩy tệp lên kho ngoài
  ◇ [lần thử < 5] → Chờ 10 giây → (quay lại bước đẩy)
  ◇ [lần thử = 5] → Giữ đường dẫn cục bộ, để tác vụ đối soát vá sau → ◉
  ↓ [đạt] Cập nhật trạng thái sẵn sàng → Báo chủ sở hữu → ◉
```

* Một ghi chú gấp góc ở vòng lặp đẩy tệp: **"tối đa 5 lần, cách nhau 10 giây"**.
* Một ghi chú ở nhánh tiến trình chết: *"mã định danh mẫu ổn định ⇒ lần chạy lại ghi
  đè, không nhân bản"*.

**Điểm phải nhìn thấy được:** ba nhánh hỏng dẫn tới **ba trạng thái kết thúc khác
nhau**, và không nhánh nào để lại dữ liệu dở dang: hỏng nhận dạng ⇒ **không tạo mẫu**;
hỏng đẩy tệp ⇒ **mẫu vẫn sẵn sàng**, chỉ thiếu bản sao; hỏng ghi nguồn sự thật ⇒
**xếp hàng lại**.

**Chú thích:** *Hình 3.17: Xử lý bất đồng bộ tin cậy và ba đường khôi phục.*

---

## HÌNH 3.18 — Bảy tầng an toàn của phân hệ

**Loại & công cụ:** infographic tầng xếp chồng · draw.io

**Phải thể hiện — bảy tầng, mỗi tầng ghi *bịt lối vòng nào*:**

| # | Tầng | Bịt lối vòng nào | Nếu bỏ tầng này |
|---|---|---|---|
| 1 | Xác thực danh tính | Người lạ vào được hệ thống | Không có gì để phân quyền |
| 2 | Phân quyền theo phạm vi | Người đúng nhưng sai vai | Mọi thành viên làm được mọi việc |
| 3 | Xác thực lại thao tác nhạy cảm | Phiên bị chiếm dụng thực hiện thao tác không hoàn tác được | Một tab bỏ quên dọn sạch được cả tổ chức |
| 4 | **Ngữ cảnh tổ chức trong phạm vi giao dịch** | Ngữ cảnh **dính lại trên kết nối** và rò sang yêu cầu kế tiếp | Một người đọc được dữ liệu của người trước trên cùng kết nối |
| 5 | **Bảo mật mức hàng** | Truy vấn **quên điều kiện lọc** | Mọi truy vấn viết thiếu đều rò, và rò im lặng |
| 6 | **Ràng buộc tham chiếu (khoá ngoại ghép)** | Bản ghi tổ chức A **trỏ sang** tài nguyên tổ chức B | Cơ sở dữ liệu không phản đối vì khoá vẫn tồn tại |
| 7 | Truy cập tạo tác có nhận biết tổ chức | Đầu ra rời khỏi phạm vi cơ sở dữ liệu: bộ nhớ tiến trình, kết nối dài, hệ tệp | Cách ly ở tầng CSDL **không tự lan sang** ba nơi đó |

* Vẽ **một mũi tên "tấn công"** xuyên từ trên xuống, bị chặn ở từng tầng, mỗi điểm
  chặn ghi tên lối vòng.
* Tầng 4, 5, 6 vẽ **viền đậm** — đây là ba tầng cưỡng chế ở tầng cơ sở dữ liệu.
* Tầng 7 vẽ viền **nét chấm** kèm nhãn *"mức bảo đảm thấp hơn: dựa vào cấu trúc lưu
  trữ và kiểm tra ở tầng ứng dụng"*.

**Điểm phải nhìn thấy được:** bảy tầng **không phải bảy lớp giống nhau chồng lên cho
chắc** — mỗi tầng bịt **một lối vòng khác nhau** mà sáu tầng còn lại để hở.

**Chú thích:** *Hình 3.18: Bảy tầng an toàn và lối vòng mà mỗi tầng bịt.*

---

## HÌNH 3.19 — Kiến trúc ứng dụng chi tiết

**Loại & công cụ:** sơ đồ khối bốn tầng · draw.io

**Phải thể hiện — bốn tầng nội bộ, xếp dọc:**

```
TẦNG 1 — TRÌNH BÀY
  Ứng dụng đơn trang React · lớp gọi API · lớp đa ngôn ngữ
  Trích điểm mốc bằng WebAssembly   ← chạy TẠI MÁY KHÁCH

TẦNG 2 — GIAO TIẾP VÀ KIỂM SOÁT TRUY CẬP
  Cổng vào (reverse proxy)  →  địa chỉ IP thật lấy ở đây
  Tầng trung gian: CỔNG MẶC ĐỊNH TỪ CHỐI  ← chạy TRƯỚC bộ định tuyến
  Tầng trung gian: phân giải phiên và đặt phạm vi tổ chức
  27 bộ định tuyến / 228 điểm cuối

TẦNG 3 — NGHIỆP VỤ
  Danh tính & Phiên · Tổ chức & Phân quyền · Danh mục & Registry
  Thu nhận & Xử lý · Đồng thuận & Quản trị dữ liệu · Toàn vẹn & Vận hành

TẦNG 4 — TRUY CẬP DỮ LIỆU
  MỘT khối quản lý ngữ cảnh duy nhất  ← nơi duy nhất đặt được phạm vi tổ chức
  Tầng truy cập PostgreSQL · Tầng truy cập hệ tệp (hàm duyệt dùng chung có chốt chặn)
  Tầng gửi tác vụ nền
```

* Ô *"MỘT khối quản lý ngữ cảnh duy nhất"* vẽ **viền đậm nhất toàn hình**, kèm ghi
  chú: *"một bảo đảm chỉ mạnh bằng số lối vào của nó"*.
* Ô *"cổng mặc định từ chối"* ghi thêm: *"điểm cuối mới quên khai báo quyền ⇒ tự động
  yêu cầu xác thực"*.

**Điểm phải nhìn thấy được:** phạm vi tổ chức được đặt ở **đúng một chỗ** trong toàn
bộ mã nguồn. Nếu hình cho thấy nhiều đường vào tầng dữ liệu, hình đã mô tả sai kiến trúc.

**Chú thích:** *Hình 3.19: Kiến trúc ứng dụng chi tiết theo bốn tầng nội bộ.*

---

## HÌNH 3.20 — Cách ly tổ chức nhiều tầng

**Loại & công cụ:** sơ đồ khối có chú giải · draw.io

**Phải thể hiện — bốn tầng cách ly, kèm số liệu đo được:**

```
TẦNG 1 — Cột phân biệt
   36/36 bảng thuộc tổ chức mang cột định danh tổ chức
   ⚠ một mình thì CHỈ LÀ SIÊU DỮ LIỆU — không có gì buộc truy vấn dùng nó

TẦNG 2 — Chính sách bảo mật mức hàng
   35/36 bảng có chính sách · ngoại lệ DUY NHẤT: bảng yêu cầu dọn sạch dữ liệu
   Cùng MỘT khuôn cho cả 35 chính sách:
      (phạm vi hệ thống = bật)  HOẶC  (định danh tổ chức = ngữ cảnh phiên)
   ⚠ đọc biến ở dạng "cho phép thiếu" ⇒ biến chưa gán cho ra NULL ⇒ 0 hàng

TẦNG 3 — Phạm vi giao dịch
   Lệnh gán giới hạn trong giao dịch, trong MỘT khối quản lý ngữ cảnh
   ⚠ lệnh gán thường sẽ DÍNH LẠI trên kết nối và rò sang yêu cầu kế tiếp

TẦNG 4 — Tách vai cơ sở dữ liệu
   Vai chạy: không có quyền cấu trúc · KHÔNG phải siêu người dùng · KHÔNG sở hữu bảng
   ⚠ lệnh vô hiệu hoá chính sách LÀ một lệnh cấu trúc
```

* Bên phải đặt **một cột riêng**: `MẶT PHẲNG TỆP`, vẽ **nét chấm**, ghi: *"cách ly
  bằng cấu trúc thư mục + một hàm duyệt dùng chung có chốt chặn — mức bảo đảm **thấp
  hơn** mặt phẳng cơ sở dữ liệu"*.
* Dưới cùng ghi biểu thức bất biến:

$$\text{Yêu cầu}(T_A) \Rightarrow \neg\,\text{Dữ liệu}(T_B)$$

**Điểm phải nhìn thấy được:** cả bốn tầng nằm **dưới** tầng mà lập trình viên có thể
quên. Đó là toàn bộ lý do thiết kế này tồn tại.

**Chú thích:** *Hình 3.20: Bốn tầng cách ly tổ chức và mặt phẳng tệp với mức bảo đảm
khác.*

---

## HÌNH 3.21 — Ranh giới xử lý đồng bộ và bất đồng bộ

**Loại & công cụ:** sơ đồ khối có đường phân cách · draw.io

**Phải thể hiện:**

```
╔══ TRONG VÒNG ĐỜI MỘT YÊU CẦU HTTP ══════════════════════╗
║  Mở phạm vi tổ chức                                      ║
║  Kiểm đồng thuận người ký                                ║
║  Kiểm hạn mức tổ chức                                    ║
║  Ghi bản ghi mẫu (trạng thái chờ xử lý)                  ║
║  Đẩy tác vụ vào hàng đợi                                 ║
║  Trả mã tác vụ            ← người dùng KHÔNG chờ, < 1 giây║
╚══════════════════════════════════════════════════════════╝
                    ▼   producer → broker → worker
╔══ NGOÀI VÒNG ĐỜI YÊU CẦU ════════════════════════════════╗
║  Ghi kho thô                                             ║
║  Cắt cửa sổ · chuẩn hoá · tăng cường                     ║
║  Chấm chất lượng                                         ║
║  Ghi tệp đặc trưng                                       ║
║  Nối vào nguồn sự thật, phản chiếu sang cơ sở dữ liệu    ║
║  Đẩy lên kho lưu trữ ngoài (5 lần thử)                   ║
╚══════════════════════════════════════════════════════════╝
```

* Bên trái đặt bảng **tiêu chí quyết định** một thao tác thuộc bên nào:

| Thuộc bên đồng bộ khi | Thuộc bên bất đồng bộ khi |
|---|---|
| Kết quả quyết định việc **có ghi hay không** | Kết quả chỉ **làm giàu** bản ghi đã có |
| Thời gian chạy **có cận trên nhỏ** | Thời gian chạy **phụ thuộc dữ liệu vào** |
| Hỏng thì phải **từ chối yêu cầu** | Hỏng thì **thử lại được** |

* Ghi chú ở dưới: *"đánh đổi: gộp các bước vào một tác vụ nền ⇒ mất khả năng chạy lại
  từng bước riêng, đổi lấy việc không phải quản lý chuỗi trạng thái trung gian"*.

**Điểm phải nhìn thấy được:** **ba phép kiểm cổng nằm ở bên đồng bộ**. Đẩy chúng sang
bên bất đồng bộ nghĩa là hệ thống đã ghi dữ liệu trước rồi mới hỏi có được phép ghi
không.

**Chú thích:** *Hình 3.21: Ranh giới xử lý đồng bộ và bất đồng bộ, kèm tiêu chí phân
định.*

---

# PHẦN D — MÔ HÌNH DỮ LIỆU (Hình 3.22 – 3.31)

## HÌNH 3.22 — Mô hình dữ liệu mức khái niệm (CDM)

**Loại & công cụ:** CDM, ký pháp **Crow's Foot** · PowerDesigner

**Quy tắc bắt buộc:** **không có kiểu dữ liệu SQL, không có khoá, không có chỉ mục**.
Chỉ thực thể, thuộc tính nghiệp vụ và lực lượng quan hệ.

**Rút 59 bảng về 19 thực thể nghiệp vụ:**

| # | Thực thể | Gộp từ |
|---|---|---|
| 1 | Người dùng | `users` |
| 2 | Thông tin xác thực | 5 bảng token và mã một lần |
| 3 | Tổ chức | `tenants` |
| 4 | Không gian làm việc **◐** | `workspaces` |
| 5 | Dự án **◐** | `projects` |
| 6 | Tư cách thành viên | `memberships` |
| 7 | Vai | `roles` |
| 8 | Quyền | `permissions` |
| 9 | Lời mời | `tenant_invitations` |
| 10 | **Người ký** | `signers` |
| 11 | **Lớp ký hiệu** | `classes` |
| 12 | Phiên thu | `capture_sessions` |
| 13 | **Mẫu** | `samples` |
| 14 | Bản tải lên thô | `raw_uploads` |
| 15 | Phương ngữ | `dialects` |
| 16 | Phiên bản danh mục | `registry_versions` |
| 17 | Tác vụ huấn luyện | `training_jobs` |
| 18 | **Văn bản pháp lý** | `legal_documents` |
| 19 | **Đồng thuận** | `user_consents` + `signer_consents` — **vẽ HAI thực thể riêng** |

**Không lên CDM:** mọi bảng lịch sử (`*_aliases`, `*_events`, lịch sử gửi, chỉ số
theo chu kỳ), bảng nối thuần, bảng trạng thái đồng bộ.

**Quan hệ then chốt phải có, kèm lực lượng Crow's Foot:**

```
Tổ chức       ──1──<──n── Người ký
Tổ chức       ──1──<──n── Lớp ký hiệu
Người ký      ──1──<──n── Phiên thu ──1──<──n── Mẫu
Lớp ký hiệu   ──1──<──n── Mẫu
Người dùng    ──n──>──<──n── Tổ chức     (qua Tư cách thành viên)
Tư cách thành viên ──1──<──n── Lần gán vai ──n──>──1── Vai ──n──>──<──n── Quyền
Phiên bản danh mục ──1──<──n── Tác vụ huấn luyện
Văn bản pháp lý ──1──<──n── Chấp thuận của người dùng
Văn bản pháp lý ──1──<──n── Đồng thuận của người ký
Người ký      ──1──<──n── Đồng thuận của người ký
```

**Điểm phải nhìn thấy được — ba điều:**
1. **Người dùng và Người ký là hai thực thể khác nhau**, và **Mẫu nối tới CẢ HAI** —
   một cạnh cho tài khoản vận hành, một cạnh cho chủ thể dữ liệu.
2. **Hai thực thể đồng thuận tách riêng.** Gộp chúng là sai về ngữ nghĩa pháp lý.
3. Không gian làm việc và Dự án mang nhãn **◐**.

**Chú thích:** *Hình 3.22: Mô hình dữ liệu mức khái niệm — 19 thực thể nghiệp vụ.*

---

## HÌNH 3.23 — Tổng quan mô hình dữ liệu mức luận lý (LDM)

**Loại & công cụ:** sơ đồ khối · draw.io

**Phải thể hiện:** bảy khối mô-đun, mỗi khối ghi tên nhóm và **số bảng thật**:

| Khối | Nhóm | Số bảng | Chịu ranh giới tổ chức |
|---|---|:--:|---|
| M1 | Danh tính & Truy cập | 8 | Một phần |
| M2 | Tổ chức & Phân quyền | 10 (+1 khung nhìn) | Có |
| M3 | Kho dữ liệu mẫu | 6 | **Có — trọng tâm** |
| M4 | Danh mục & Registry | 11 | Có, trừ 3 bảng danh mục hệ thống |
| M5 | Huấn luyện & Mô hình | 3 | Có |
| M6 | Dịch vụ tổ chức & Tích hợp | 12 | Có |
| M7 | Pháp lý, Kiểm toán & Nền tảng | 9 | Một phần |
| | **Tổng** | **59** | |

* **Bốn cạnh giữa các khối**, mỗi cạnh có nhãn: `M2 → M3` ranh giới tổ chức ·
  `M4 → M3` lớp từ vựng · `M3 → M5` dữ liệu huấn luyện · `M7 → M3` đồng thuận chi
  phối phát hành.
* Khối chịu và không chịu ranh giới tổ chức phân biệt bằng **kiểu viền**, không bằng
  nền màu.
* Ghi ở góc: **123 khoá ngoại · 24 khoá ghép · 35 chính sách · 6 trigger**.

**Chú thích:** *Hình 3.23: Tổng quan mô hình luận lý theo bảy nhóm mô-đun.*

---

## HÌNH 3.24 — LDM Mô-đun A: Danh tính, Tổ chức và Phân quyền

**Loại & công cụ:** LDM Crow's Foot · PowerDesigner

**Phải thể hiện — 18 bảng của M1 và M2, đủ tên cột khoá:**

```
users ──1──<──n── memberships ──1──<──n── role_assignments ──n──>──1── roles
   │                   │  ▲                                              │
   │                   │  └── tự trỏ (parent_membership_id, user_id)     │
   │                   │                                                 ▼
   │              tenants ──1──<──n── workspaces ──1──<──n── projects   role_permissions
   │                   │                                        │            │
   │                   └──1──<──n── tenant_invitations          │            ▼
   │                                                            ▼       permissions
   └── refresh_tokens · password_reset_tokens · verification_codes
       user_totp · user_recovery_codes · user_action_passcodes · api_keys
                                                    project_allocations
```

**Ba điểm bắt buộc:**
1. `memberships` là **MỘT** bảng đa hình với cột cấp phạm vi, **không phải ba bảng**.
   **Không được vẽ** `workspace_members` hay `project_members` — hai bảng đó không tồn tại.
2. `tenant_members` vẽ bằng **nét đứt** kèm nhãn `«view»` — nó là khung nhìn trên lát
   cắt của `memberships`, không phải bảng.
3. `roles.tenant_id` ghi rõ **cho phép trống**, kèm chú giải: *"trống = vai dựng sẵn
   của nền tảng"*. Ở CDM đây là **một** thực thể, không phải hai.

**Đánh dấu:** bảng có chính sách cách ly dùng một ký hiệu thống nhất; ghi rõ
`role_assignments` **không có** cột định danh tổ chức và **không** bật chính sách, kèm
ghi chú: *"phạm vi kế thừa gián tiếp qua tư cách thành viên"*.

**Chú thích:** *Hình 3.24: LDM mô-đun Danh tính, Tổ chức và Phân quyền.*

---

## HÌNH 3.25 — LDM Mô-đun B: Danh mục và Registry

**Loại & công cụ:** LDM Crow's Foot · PowerDesigner

**Phải thể hiện — 11 bảng của M4, chia ba vùng:**

```
VÙNG 1 — Danh mục nền tảng (không có định danh tổ chức)
   languages · regions

VÙNG 2 — Danh mục của tổ chức (có định danh tổ chức, có chính sách cách ly)
   dialects ──1──<──n── dialect_aliases
   dialects ──tự trỏ── merged_into
   recognition_profiles · vocabulary_groups · vocabulary_registry_meta
   registry_versions        ← bất biến theo QUY ƯỚC, KHÔNG có trigger

VÙNG 3 — DANH MỤC HỆ THỐNG  (tên bảng community_* là DI SẢN)
   community_dialects · community_profiles · community_versions
   ⚠ KHÔNG có định danh tổ chức, KHÔNG có chính sách cách ly
   ⚠ ĐÂY KHÔNG PHẢI mặt phẳng Cộng đồng
```

* **Một mũi tên một chiều** từ Vùng 3 sang Vùng 2, nhãn *"sao chép MỘT LẦN, lúc khởi
  tạo tổ chức"*.
* **Một mũi tên gạch chéo** theo chiều ngược lại, nhãn *"lúc chạy KHÔNG có đường rơi
  ngược — thiếu dữ liệu thì DỪNG"*.
* Một ghi chú riêng: *"mặt phẳng Cộng đồng là một HÀNG của bảng tổ chức
  (`tenant_type='COMMUNITY'`), không phải ba bảng này"*.

**Điểm phải nhìn thấy được:** ba bảng `community_*` chứa **chỉ cấu hình** — không mẫu,
không đồng thuận, không thông tin quy kết.

**Chú thích:** *Hình 3.25: LDM mô-đun Danh mục và Registry, ba vùng và luật không rơi
ngược.*

---

## HÌNH 3.26 — LDM Mô-đun C: Thu nhận, Mẫu và Nguồn gốc

**Loại & công cụ:** LDM Crow's Foot · PowerDesigner

**Phải thể hiện — 6 bảng của M3 cộng hai bảng liên quan của M5:**

```
signers ──1──<──n── capture_sessions ──1──<──n── samples
   │                       │                        │
   │                       └────────────────────────┤
   └──1──<──n── signer_aliases                      │
                                                    │
classes ──1──<──n── samples ────────────────────────┘
   │
   └──1──<──n── capture_sessions

raw_uploads  ╌╌╌╌ (KHÔNG có khoá ngoại tới samples) ╌╌╌╌ samples

training_jobs ──1──<──n── training_job_classes
```

**Bốn điểm bắt buộc:**
1. **Vẽ RÕ khoá ngoại ghép**: ghi cặp cột trên cạnh, ví dụ
   `samples(tenant_id, class_uid) → classes(tenant_id, class_uid)`.
2. **Hai cạnh khác nhau từ `samples`**: một tới `signers` (chủ thể dữ liệu, phủ
   43,4 %), một tới `users` qua cột tài khoản vận hành (phủ 95,7 %). Đây là điểm
   **phải nhìn thấy được** của hình.
3. Quan hệ `raw_uploads ─ samples` vẽ **nét chấm mảnh** kèm nhãn *"không cưỡng chế ở
   tầng ràng buộc"*.
4. Ghi cạnh `classes`: **khoá duy nhất 5 cột** `(tenant_id, slug, language, dialect,
   region)`.

**Chú thích:** *Hình 3.26: LDM mô-đun Thu nhận, Mẫu và Nguồn gốc.*

---

## HÌNH 3.27 — LDM Mô-đun D: Quản trị dữ liệu và Dịch vụ nền tảng

**Loại & công cụ:** LDM Crow's Foot · PowerDesigner

**Phải thể hiện — 21 bảng của M6 và M7, chia ba cụm:**

```
CỤM PHÁP LÝ VÀ ĐỒNG THUẬN
   legal_document_drafts ──> legal_documents
   legal_documents ──1──<──n── user_consents      (khoá ghép kind, version)
   legal_documents ──1──<──n── signer_consents    (khoá ghép kind, version)
   signers ──1──<──n── signer_consents
   legal_document_events                          (chỉ thêm, có trigger)

CỤM DỊCH VỤ TỔ CHỨC
   plans ──1──<──n── tenant_subscriptions
   tenants ──1──<──n── tenant_usage_daily · tenant_exports · tenant_purges
   webhook_endpoints ──1──<──n── webhook_deliveries
   support_tickets ──1──<──n── support_messages
   notifications · event_outbox

CỤM NỀN TẢNG
   audit_log · platform_settings · sot_authorized_keys
   schema_migrations · google_sheets_sync_status
```

**Ba điểm bắt buộc:**
1. `user_consents` và `signer_consents` là **hai thực thể tách bạch**, mỗi cái có ghi
   chú riêng: *chấp thuận điều khoản dịch vụ* vs **đồng thuận của chủ thể dữ liệu —
   chi phối đường phát hành**.
2. `legal_documents` **không có bảng phiên bản con**; định danh nghiệp vụ là cặp
   `(kind, version)` trên chính bảng đó. **Không vẽ** một thực thể *Phiên bản văn bản
   pháp lý* riêng.
3. `tenant_purges` đánh dấu là **ngoại lệ duy nhất** không bật chính sách cách ly.

**Chú thích:** *Hình 3.27: LDM mô-đun Quản trị dữ liệu và Dịch vụ nền tảng.*

---

## HÌNH 3.28 – 3.31 — PDM bốn mô-đun

**Loại & công cụ:** PDM · PowerDesigner · sinh từ lược đồ thật, **không vẽ tay**

Bốn hình PDM tương ứng bốn mô-đun LDM ở trên:

| Hình | Mô-đun | Bảng |
|---|---|:--:|
| 3.28 | A — Danh tính, Tổ chức và Phân quyền | 18 |
| 3.29 | B — Danh mục và Registry | 11 |
| 3.30 | C — Thu nhận, Mẫu và Nguồn gốc | 9 |
| 3.31 | D — Quản trị dữ liệu và Dịch vụ nền tảng | 21 |

**Khác LDM ở bốn điểm — và chỉ bốn điểm này:**
1. **Kiểu dữ liệu vật lý** cho mọi cột (`Text`, `Uuid`, `Timestamptz`, `Boolean`,
   `Integer`, `Real`, `Jsonb`, `Varchar(n)`).
2. **Chỉ mục**, kèm chỉ mục riêng phần. Bắt buộc có ba chỉ mục đáng nói:
   * `uq_classes_tenant_slug_lang_dialect_region` — khoá duy nhất **5 cột**;
   * `uq_tenants_single_community` — bảo đảm **nhiều nhất một** tenant cộng đồng;
   * `uq_role_assignments_scoped` và `uq_role_assignments_system` — **hai** chỉ mục
     riêng phần, phân theo việc tư cách thành viên có trống hay không.
3. **Chính sách bảo mật mức hàng**, ghi bằng khuôn chữ `«RLS»` trên bảng có bật, kèm
   một ghi chú chung ghi khuôn vị từ dùng cho cả 35 chính sách.
4. **Sáu trigger**, ghi bằng khuôn chữ `«trigger»` trên đúng sáu bảng: hai trên nhóm
   văn bản pháp lý, bốn trên nhóm phân quyền.

**Quy tắc trình bày:** PDM trong thân bài chỉ vẽ **cột khoá và cột ràng buộc**; danh
sách cột đầy đủ nằm ở Phụ lục A-2 Từ điển dữ liệu. **PDM đầy đủ cả 59 bảng đặt ở phụ
lục**, không đặt trong thân chương.

**Chú thích mẫu:** *Hình 3.28: PDM mô-đun Danh tính, Tổ chức và Phân quyền.*

---

# PHẦN E — LUỒNG NGHIỆP VỤ CHI TIẾT (Hình 3.32 – 3.39)

## HÌNH 3.32 — Sequence: Phân quyền theo phạm vi tổ chức

**Loại & công cụ:** sequence diagram · PlantUML

**Sáu đường đời:** `Người dùng` · `Cổng vào` · `Tầng trung gian` · `Bộ định tuyến` ·
`Tầng truy cập dữ liệu` · `PostgreSQL`

**Trình tự:**

```
 1  Người dùng → Cổng vào       : yêu cầu HTTPS
 2  Cổng vào → Tầng trung gian  : chuyển tiếp, kèm ĐỊA CHỈ IP THẬT
 3  Tầng trung gian             : đường dẫn có trong danh sách ngoại lệ công khai?
    alt [không có] → BẮT BUỘC xác thực          ← cổng mặc định từ chối
    alt [có]       → cho qua
 4  Tầng trung gian             : phân giải phiên → xác định tài khoản
 5  Tầng trung gian             : xác định tổ chức của yêu cầu
 6  Tầng trung gian → Bộ định tuyến : chuyển tiếp kèm phạm vi
 7  Bộ định tuyến → Tầng dữ liệu    : gọi nghiệp vụ
 8  Tầng dữ liệu → PostgreSQL       : MỞ GIAO DỊCH
 9  Tầng dữ liệu → PostgreSQL       : ĐẶT NGỮ CẢNH TỔ CHỨC, giới hạn trong giao dịch
10  Tầng dữ liệu → PostgreSQL       : truy vấn nghiệp vụ
11  PostgreSQL                      : ÁP CHÍNH SÁCH BẢO MẬT MỨC HÀNG
12  PostgreSQL → Tầng dữ liệu       : chỉ trả hàng thuộc tổ chức đó
13  Tầng dữ liệu → PostgreSQL       : ĐÓNG GIAO DỊCH  → ngữ cảnh TỰ BIẾN MẤT
```

* Bước 8–13 vẽ trong **một khung `group`** nhãn *"một khối quản lý ngữ cảnh duy nhất"*.
* Bước 11 vẽ **thông điệp tự gọi** trên đường đời cơ sở dữ liệu, kèm ghi chú in đậm.

**Ba nhánh `alt` phải có:**

| Nhánh | Kết quả | Ghi chú trên hình |
|---|---|---|
| Không có phiên đăng nhập | 401, dừng ở tầng trung gian | không tới được bộ định tuyến |
| Có phiên, **sai tổ chức** | **0 hàng** | chính sách chặn ở tầng cơ sở dữ liệu, **không** ở tầng ứng dụng |
| Tổ chức **Cộng đồng** | **đi đúng cùng một đường** | trạng thái dự trữ **không** bỏ qua phép kiểm quyền |

**Điểm phải nhìn thấy được:** nhánh thứ ba. Cộng đồng là một tổ chức dự trữ và nó
chịu **đúng** chuỗi kiểm tra như mọi tổ chức khác — không có đường tắt nào.

**Chú thích:** *Hình 3.32: Trình tự phân quyền theo phạm vi tổ chức.*

---

## HÌNH 3.33 — Activity: Đăng ký và cập nhật lớp ký hiệu

**Loại & công cụ:** activity diagram · PlantUML

**Phải thể hiện:**

```
● bắt đầu
↓ Nhập nhãn, ngôn ngữ, phương ngữ, VÙNG MIỀN, số bàn tay, chỉ tiêu thu
↓ Sinh nhãn chuẩn hoá từ nhãn nhập
   📎 giữ phân biệt các chữ cái tiếng Việt có dấu phụ cho bảng chữ cái ngón tay
◇ [người gọi không có vai biên tập trên tổ chức CỦA MÌNH] → Từ chối, ghi kiểm toán → ⊗
   📎 vai đọc trên tổ chức của người gọi, KHÔNG đọc trên tổ chức nêu trong yêu cầu
↓ [đủ vai]
◇ [vượt hạn mức lớp hoặc vượt giới hạn tần suất] → Từ chối, nêu hạn mức → ⊗
↓ [trong hạn mức]
↓ KIỂM TRÙNG THEO ĐỦ NĂM CỘT
◇ [trùng cả năm] → Từ chối; số hiệu phiên bản danh mục KHÔNG đổi → ⊗
↓ [khác ít nhất một cột]
↓ Gán mã định danh lớp và chỉ số lớp
↓ Ghi hàng lớp trong phạm vi tổ chức
↓ TĂNG số hiệu phiên bản danh mục của tổ chức
↓ Ghi bản ghi kiểm toán
◉ kết thúc

── NHÁNH CẬP NHẬT (vẽ song song, dùng chung phần kiểm) ──
↓ Sửa siêu dữ liệu
   📎 mã định danh lớp và CHỈ SỐ LỚP GIỮ NGUYÊN
   📎 đổi chỉ số lớp ⇒ mô hình đã huấn luyện nói về không gian nhãn khác lúc suy luận
```

**Điểm phải nhìn thấy được:** phép kiểm trùng chạy trên **đủ năm cột**, và **vùng
miền là một trong năm**. Kiểm bốn cột sẽ từ chối đúng những thứ hệ thống cần cho phép.

**Chú thích:** *Hình 3.33: Đăng ký và cập nhật lớp ký hiệu.*

---

## HÌNH 3.34 — Infographic: Tiến hoá danh mục từ vựng của một tổ chức

**Loại & công cụ:** infographic dòng thời gian · draw.io

**Phải thể hiện — bốn mốc theo trục thời gian ngang:**

```
MỐC 1 — Khởi tạo tổ chức
   Danh mục hệ thống ──sao chép MỘT LẦN──> Danh mục của tổ chức
   Ghi lại: phiên bản danh mục hệ thống đã sao chép
   ⚠ Đây là KẾ THỪA, không phải tham chiếu

MỐC 2 — Tổ chức mở rộng danh mục của mình
   Thêm lớp riêng · thêm phương ngữ riêng · sửa siêu dữ liệu
   ⚠ DANH MỤC HỆ THỐNG KHÔNG ĐỔI MỘT DÒNG NÀO

MỐC 3 — Chốt phiên bản danh mục
   Ảnh chụp bất biến + mã băm nội dung
   ⚠ bất biến theo QUY ƯỚC ứng dụng, KHÔNG có trigger cưỡng chế

MỐC 4 — Tác vụ huấn luyện ghim phiên bản
   Chạy lại sáu tháng sau vẫn dùng ĐÚNG tập nhãn của lần đầu
   ⚠ ghim KHÔNG GIAN NHÃN, không ghim nội dung bộ dữ liệu
```

* Dưới trục thời gian đặt **một mũi tên gạch chéo** đi ngược từ Mốc 2 về Mốc 1, nhãn:
  *"lúc chạy KHÔNG có đường đọc ngược về danh mục hệ thống — thiếu thì DỪNG"*.

**Điểm phải nhìn thấy được:** đây là cam kết *"tổ chức mở rộng được danh mục dùng
chung mà không sửa bản gốc"*, và nó đạt được bằng **thiếu vắng một đường ghi** chứ
không bằng một phép kiểm — cách bảo đảm mạnh hơn.

**Chú thích:** *Hình 3.34: Tiến hoá danh mục từ vựng của một tổ chức qua bốn mốc.*

---

## HÌNH 3.35 — Sequence: Thu trực tiếp qua camera (bản chi tiết theo thuật toán 3.2)

**Loại & công cụ:** sequence diagram · PlantUML

Hình này là bản **chi tiết hơn Hình 3.13**, bám đúng 15 bước của thuật toán 3.2.
Hình 3.13 dùng ở mục tổng quan; hình này dùng ở mục thiết kế chức năng thu nhận.

**Đường đời:** `Người đóng góp` · `Trình duyệt` · `Bộ trích điểm mốc «wasm»` ·
`Dịch vụ ứng dụng` · `PostgreSQL` · `Hàng đợi` · `Tiến trình nền` · `Kho tệp`

**Ánh xạ 15 bước sang thông điệp:**

| Bước thuật toán | Trên hình |
|---|---|
| 1–2 Nạp siêu dữ liệu lớp, người ký, phiên thu | Trình duyệt → Dịch vụ → PostgreSQL |
| 3 Kiểm quyền của người đóng góp | Dịch vụ → PostgreSQL, trong phạm vi tổ chức |
| 4 Xin quyền camera | Trình duyệt → Người đóng góp |
| 5–7 Phát hiện điểm mốc từng khung · chuyển thành biểu diễn · nạp vào bộ đệm | **vòng lặp `loop` trên đường đời Trình duyệt và Bộ trích điểm mốc** |
| 8 Tính chỉ số chất lượng lúc thu | tự gọi trên Trình duyệt |
| 9 Trình bản thu cho người đóng góp xem lại | Trình duyệt → Người đóng góp |
| 10 Gửi chuỗi và siêu dữ liệu | Trình duyệt → Dịch vụ |
| 11 Kiểm quan hệ tổ chức ở phía máy chủ | Dịch vụ → PostgreSQL |
| 12 Tạo trạng thái mẫu | Dịch vụ → PostgreSQL |
| 13 Xếp lịch xử lý bổ sung | Dịch vụ → Hàng đợi |
| 14 Ghi tạo tác đặc trưng | Tiến trình nền → Kho tệp |
| 15 Cập nhật trạng thái mẫu | Tiến trình nền → PostgreSQL |

* Vòng lặp bước 5–7 phải ghi **điều kiện thoát bằng số**: *"tới khi đủ 60 khung hoặc
  người dùng bấm dừng"*.
* Khối `«wasm»` ghi nhãn **`local`** và có ghi chú: *"video không rời máy người dùng"*.

**Chú thích:** *Hình 3.35: Trình tự chi tiết thu mẫu trực tiếp qua camera.*

---

## HÌNH 3.36 — Sequence: Xử lý bản ghi nguồn (bản chi tiết theo thuật toán 3.3)

**Loại & công cụ:** sequence diagram · PlantUML

**Ánh xạ 10 bước của thuật toán 3.3:**

| Bước | Trên hình | Ghi chú bắt buộc |
|---|---|---|
| 1 Kiểm kiểu tệp và quyền gửi | Dịch vụ tự gọi | tệp hỏng **không** chặn các tệp còn lại |
| 2 **Lưu bản ghi nguồn** | Dịch vụ → Kho tệp thô | **TRƯỚC mọi bước dẫn xuất** |
| 3 Ghi siêu dữ liệu nguồn | Dịch vụ → PostgreSQL | |
| 4 Tạo tác vụ xử lý bất đồng bộ | Dịch vụ → Hàng đợi | ranh giới đồng bộ/bất đồng bộ |
| 5 Trích điểm mốc | Tiến trình nền tự gọi | **ở máy chủ**, khác Hình 3.35 |
| 6 Chuẩn hoá biểu diễn dẫn xuất | Tiến trình nền tự gọi | |
| 7 Tính chỉ số chất lượng | Tiến trình nền tự gọi | |
| 8 Ghi tạo tác đặc trưng dẫn xuất | Tiến trình nền → Kho tệp | kèm tệp mô tả đi kèm |
| 9 Cập nhật trạng thái xử lý mẫu | Tiến trình nền → PostgreSQL | |
| 10 **Giữ bản nguồn để xử lý lại** | ghi chú trên Kho tệp thô | *"theo luật lưu giữ"* |

**Điểm phải nhìn thấy được:** bước 2 và bước 10 là **hai vế của cùng một quyết định
thiết kế**. Đặt cạnh Hình 3.35, người đọc phải thấy ngay: đường camera **không xử lý
lại được**, đường tệp **xử lý lại được**.

**Chú thích:** *Hình 3.36: Trình tự chi tiết xử lý bản ghi nguồn.*

---

## HÌNH 3.37 — State machine: Vòng đời một mẫu dữ liệu

**Loại & công cụ:** state machine diagram · PlantUML

**Sáu trạng thái, dùng đúng tên trạng thái trong cài đặt:**

```
        ●
        ↓ [ghi bản ghi mẫu]
   ┌─────────────┐
   │  CHỜ XỬ LÝ  │
   └──────┬──────┘
          ↓ [tiến trình nền nhận việc]
   ┌─────────────┐
   │  ĐANG XỬ LÝ │────[không phát hiện được bàn tay]───┐
   └──────┬──────┘                                     ▼
          ↓ [xử lý xong]                        ┌────────────┐
   ┌─────────────┐                              │  THẤT BẠI  │
   │  SẴN SÀNG   │◄────[khôi phục từ thùng rác]─┴─────┬──────┘
   └──────┬──────┘                                    │
          ↓ [xoá mềm]                                 ↓ [xử lý lại — CHỈ đường tệp]
   ┌─────────────┐                              (về ĐANG XỬ LÝ)
   │   ĐÃ XOÁ    │
   └──────┬──────┘
          ↓ [dọn hẳn thùng rác]
   ┌─────────────┐
   │  DỌN HẲN    │  ← trạng thái cuối, KHÔNG có cung quay ra
   └──────┬──────┘
          ◉
```

**Bốn ghi chú bắt buộc:**
1. Cung `ĐÃ XOÁ → SẴN SÀNG` là **khôi phục được**; đây là lý do tệp vẫn được giữ ở
   trạng thái đã xoá.
2. Cung `ĐÃ XOÁ → DỌN HẲN` là **thao tác duy nhất chạm tới tệp trên lưu trữ**.
3. Cung xử lý lại từ `THẤT BẠI` **chỉ tồn tại với đường tải tệp**; với đường camera
   không có bản nguồn nên không xử lý lại được.
4. Trạng thái `THẤT BẠI` **không tạo hàng mẫu rác** — hàng mẫu vẫn tồn tại nhưng mang
   trạng thái thất bại kèm lý do.

**Trước khi vẽ:** đối chiếu lại tên trạng thái với cột trạng thái trong bảng mẫu
(`PENDING` / `PROCESSING` / `READY` / `FAILED`) để tên trên hình khớp cài đặt.

**Chú thích:** *Hình 3.37: Máy trạng thái vòng đời một mẫu dữ liệu.*

---

## HÌNH 3.38 — Mô hình nguồn gốc, đồng thuận và phát hành có kiểm soát

**Loại & công cụ:** sơ đồ khối kết hợp mô hình dữ liệu · draw.io

**Phải thể hiện — chuỗi nguồn gốc ngang, nhánh đồng thuận dọc:**

```
CHUỖI NGUỒN GỐC (ngang, nét liền)
  Người ký ──> Phiên thu ──> Mẫu ──> Bản tải lên thô / Biểu diễn dẫn xuất ──> Bản phát hành

NHÁNH ĐỒNG THUẬN (dọc, cắt ngang chuỗi tại điểm PHÁT HÀNH)
  Người ký ──> Đồng thuận người ký ──> ba mức tăng dần:
        [1] dùng nội bộ để huấn luyện
        [2] phát hành cho nghiên cứu
        [3] đưa vào thư viện công khai

  ⟲ RÚT ĐỒNG THUẬN — mũi tên NGƯỢC CHIỀU dòng chảy chính, nét đứt
     tác động: mọi bản phát hành SAU THỜI ĐIỂM ĐÓ
     KHÔNG tác động: dữ liệu trên lưu trữ · bản phát hành đã cấp · mô hình đã huấn luyện

TOÀN VẸN (đặt ở đáy)
  SHA-256 ──> bản kê băm từng tệp        (toàn vẹn nội dung)
  Ed25519 ──> chữ ký phủ bản kê          (xác thực nguồn)
```

* Ở mắt xích `Người ký ──> Phiên thu` ghi **độ phủ đo được: 43,4 %**, kèm ghi chú:
  *"56,6 % còn lại — chuỗi nguồn gốc đứt ở đúng vị trí không dựng lại được"*.
* Ở cổng phát hành ghi: *"nối được vào đồng thuận còn hiệu lực: 11,1 % kho mẫu"*.

**Điểm phải nhìn thấy được:** nhánh rút đồng thuận chạy **ngược chiều** dòng nghiệp
vụ. Đây là thứ phân biệt nền tảng này với một công cụ thu dữ liệu thông thường, và
cũng là lý do đồng thuận không thể là một cột siêu dữ liệu thụ động.

**Chú thích:** *Hình 3.38: Mô hình nguồn gốc, ba mức đồng thuận và cổng phát hành có
kiểm soát.*

---

## HÌNH 3.39 — Quy trình xác minh tạo tác nguồn sự thật

**Loại & công cụ:** activity diagram hai làn · PlantUML

**Hai làn:** `Máy phát hành (giữ khoá riêng)` · `Máy triển khai (chỉ có khoá công khai)`

```
LÀN 1 — MÁY PHÁT HÀNH
  ● → Dựng tạo tác → Tính SHA-256 từng tệp → Viết bản kê
    → KÝ BẢN KÊ bằng Ed25519 → Đẩy lên kho lưu trữ ngoài → ⊗

LÀN 2 — MÁY TRIỂN KHAI (lúc khởi động)
  ● → Kéo bản công bố về
  ↓ Tính lại mã băm, đối chiếu bản kê
  ◇ [lệch] ──────────────> DỪNG, thoát mã lỗi chuyên biệt ──> ◉
  ↓ [khớp]
  ↓ Kiểm chữ ký phủ bản kê
  ◇ [hỏng hoặc thiếu] ────> DỪNG ──> ◉
  ↓ [hợp lệ về mật mã]
  ↓ TRA KHOÁ KÝ TRONG DANH SÁCH TIN CẬY
  ◇ [khoá lạ] ────────────> DỪNG ──> ◉
  ↓ [khoá được tin cậy]
  ↓ Hợp nhất vào cơ sở dữ liệu theo nguyên tắc CHỈ ĐIỀN, KHÔNG XOÁ
  ↓ Cho phép các dịch vụ còn lại khởi động
  ◉
```

**Bốn ghi chú bắt buộc:**
1. **Ba điểm DỪNG là ba phép kiểm khác nhau**, không thay thế được cho nhau: toàn vẹn ·
   hợp lệ mật mã · **thẩm quyền**.
2. Ở điểm dừng thứ ba ghi kịch bản tấn công: *"kẻ tấn công dựng dữ liệu khác, tính mã
   băm đúng, viết bản kê đúng, rồi **tự ký bằng khoá của hắn** — chữ ký hợp lệ về mật
   mã nhưng thẩm quyền sai"*.
3. Hàm xác minh **trả về tên khoá đã đăng ký**, không trả giá trị đúng/sai. Ghi ngay
   cạnh bước tra khoá.
4. Tập khoá tin cậy = **hợp** của bảng khoá trong cơ sở dữ liệu với danh sách khoá
   nền ghi trong mã nguồn.

**Vế thứ tư của hợp đồng — giới hạn đã biết, vẽ bằng nét đứt ở rìa hình:** *"chính
sách phiên bản: hệ thống hiện **chấp nhận** một bản công bố có số hiệu thấp hơn bản
đang dùng — đơn điệu phiên bản chưa được cưỡng chế"*.

**Chú thích:** *Hình 3.39: Quy trình công bố và xác minh tạo tác nguồn sự thật.*

---

# PHẦN F — VẬN HÀNH VÀ TRIỂN KHAI (Hình 3.40 – 3.42)

## HÌNH 3.40 — Kiến trúc nhật ký kiểm toán và nhật ký vận hành

**Loại & công cụ:** sơ đồ khối hai cột · draw.io

**Đây là một trong những hình quan trọng nhất của chương**, vì nó giải thích rằng
**bằng chứng kiểm toán** và **nhật ký chẩn đoán** phục vụ hai mục đích khác nhau và
**không thay thế được cho nhau**.

```
CỘT TRÁI — BẰNG CHỨNG KIỂM TOÁN          CỘT PHẢI — NHẬT KÝ CHẨN ĐOÁN

  Hành động nghiệp vụ                       Dịch vụ ứng dụng / Tiến trình nền / Cổng vào
        ↓                                          ↓
  Phân loại hành động kiểm toán             Nhật ký vận hành có cấu trúc
        ↓                                          ↓
  Bộ ghi kiểm toán có cấu trúc              Bộ thu gom nhật ký
    ⚠ TỪ CHỐI GHI khi thiếu phạm vi               ↓
        ↓                                    Kho nhật ký (Loki)
  Kho kiểm toán quan hệ (audit_log)                ↓
    · chỉ thêm · có định danh tổ chức        Bảng điều khiển và cảnh báo (Grafana)
    · có chính sách cách ly
        ↓
  Rà soát theo phạm vi:
    Quản trị tổ chức → trong tổ chức mình
    Quản trị nền tảng → toàn nền tảng
```

*Bảng so sánh đặt dưới hình — bắt buộc có:*

| | Bằng chứng kiểm toán | Nhật ký chẩn đoán |
|---|---|---|
| Trả lời câu hỏi | **Ai đã làm gì, lúc nào** | Vì sao hệ thống hành xử như vậy |
| Lưu ở | Bảng quan hệ, chỉ thêm | Kho nhật ký |
| Thiếu phạm vi thì | **TỪ CHỐI GHI** | vẫn ghi |
| Nhãn phân loại | không áp dụng | **phải ÍT** — đặt định danh tổ chức làm nhãn sẽ làm sập hệ thống nhật ký |
| Giữ bao lâu | theo hạn mức gói dịch vụ | theo dung lượng |
| Sửa được không | **không** | không quan trọng |

**Hai ghi chú bắt buộc:**
1. *"thà không có bản ghi còn hơn có một bản ghi sai phạm vi"* — đặt cạnh bước từ
   chối ghi.
2. *"giá trị `-1` nghĩa là **không đo được**, khác hẳn `0` nghĩa là **đo được và bằng
   không**"* — đặt ở cột phải, cạnh bảng điều khiển.

**Chú thích:** *Hình 3.40: Kiến trúc nhật ký kiểm toán và nhật ký vận hành — hai
đường tách bạch cho hai mục đích khác nhau.*

---

## HÌNH 3.41 — Quy trình cài đặt và khởi động hệ thống

**Loại & công cụ:** activity diagram · PlantUML

**Chín bước tuần tự, mỗi bước có điểm kiểm và nhánh dừng:**

```
● bắt đầu
↓ [1] Chuẩn bị máy chủ
   ◇ [thiếu biến môi trường bắt buộc] → DỪNG trước khi dựng ảnh → ◉
   ◇ [đường dẫn cơ sở không khớp địa chỉ truy cập] → DỪNG → ◉
   📎 kiểm TRƯỚC bước dựng ảnh, vì dựng ảnh mất nhiều phút
↓ [2] Tạo vùng lưu trữ bền vững
↓ [3] Khởi động PostgreSQL và Redis
   ◇ [không kết nối được] → DỪNG → ◉
↓ [4] Di trú lược đồ
   ◇ [biến đích không khớp tên cơ sở dữ liệu] → DỪNG → ◉
   📎 chốt chặn đích: chạy nhầm lên cơ sở dữ liệu sản xuất bị chặn
↓ [5] Cấp vai cơ sở dữ liệu
   📎 vai chạy: không quyền cấu trúc · không siêu người dùng · không sở hữu bảng
↓ [6] XÁC MINH TẠO TÁC NGUỒN SỰ THẬT        ← xem Hình 3.39
   ◇ [không xác minh được] → DỪNG TOÀN BỘ STACK, mã thoát chuyên biệt → ◉
↓ [7] Khởi động dịch vụ ứng dụng và tiến trình nền
   ◇ [phiên bản lược đồ lệch — CẢ HAI CHIỀU] → TỪ CHỐI KHỞI ĐỘNG → ◉
↓ [8] Khởi động giao diện và cổng vào
↓ [9] Kiểm sức khoẻ
   · kết nối cơ sở dữ liệu · kết nối hàng đợi · tiến trình nền sẵn sàng · kho lưu trữ
   ◇ [có mục không đạt] → báo mục hỏng → ◉
◉ hệ thống sẵn sàng phục vụ
```

**Điểm phải nhìn thấy được:** bước 6 là **fail-closed**. Một máy không xác thực được
danh mục thì **không được phép phục vụ** — và cái giá phải trả là khả năng sẵn sàng.
Đường sửa khi cơ chế này gây phiền là **làm cho điều kiện được thoả**, không phải làm
cho điều kiện biến mất.

**Không đưa vào hình:** lệnh shell, tên biến môi trường, cấu hình triển khai chi tiết —
những thứ đó thuộc phụ lục cài đặt.

**Chú thích:** *Hình 3.41: Quy trình cài đặt và khởi động hệ thống.*

---

## HÌNH 3.42 — Sơ đồ triển khai

**Loại & công cụ:** deployment diagram UML · draw.io

**Phải thể hiện — MỘT nút vật lý duy nhất chứa môi trường container:**

```
╔═══ MÁY CHỦ VẬT LÝ (6 nhân · 12 GB RAM · 1 GPU) ═══════════════════╗
║                                                                    ║
║  ┌─ WEB VÀ CỔNG VÀO ──────────────┐  ┌─ KHỞI TẠO TOÀN VẸN ──────┐ ║
║  │ nginx      · frontend          │  │ sot-init                  │ ║
║  └────────────────────────────────┘  │ ⚠ chạy TRƯỚC và KẾT THÚC │ ║
║                                       │   trước mọi dịch vụ khác  │ ║
║  ┌─ ỨNG DỤNG LÕI ─────────────────┐  └───────────────────────────┘ ║
║  │ backend                        │                                 ║
║  └────────────────────────────────┘  ┌─ DỊCH VỤ HẠ NGUỒN ────────┐ ║
║                                       │ realtime_service   «GPU»  │ ║
║  ┌─ DỊCH VỤ DỮ LIỆU ──────────────┐  │ trainer            «GPU»  │ ║
║  │ postgres   · redis             │  └───────────────────────────┘ ║
║  └────────────────────────────────┘                                 ║
║                                       ┌─ QUAN TRẮC ───────────────┐ ║
║  ┌─ XỬ LÝ NỀN ────────────────────┐  │ prometheus · grafana      │ ║
║  │ worker     · celery-beat       │  │ loki       · promtail     │ ║
║  └────────────────────────────────┘  └───────────────────────────┘ ║
║                                                                    ║
║  ┌─ SAO LƯU ──────────────────────┐                                ║
║  │ pg-backup                      │                                ║
║  └────────────────────────────────┘                                ║
╚════════════════════════════════════════════════════════════════════╝

VÙNG LƯU TRỮ BỀN VỮNG — vẽ TÁCH RIÊNG, ngoài khung container
   dữ liệu PostgreSQL · kho tệp đặc trưng · kho tệp thô · bản sao lưu · nhật ký
```

**Bốn quy tắc vẽ:**
1. **Tổng 15 dịch vụ**, trong đó `sot-init` là container khởi tạo chạy một lần rồi
   thoát — vẽ **nét đứt** để phân biệt với 14 dịch vụ thường trực.
2. **Mũi tên phụ thuộc khởi động** từ `sot-init` tới `backend` và `worker` vẽ **khác
   kiểu** với mũi tên gọi thông thường.
3. Hai container gắn GPU ghi khuôn chữ `«GPU»`.
4. **Vùng lưu trữ bền vững vẽ tách hẳn** khỏi khung container, vì chúng sống sót qua
   việc dựng lại container.

**Ghi ở góc hình:** hạn mức bộ nhớ của từng container là **bắt buộc**, do ràng buộc
một máy chủ 12 GB — một dịch vụ rò bộ nhớ không được phép giết cả máy.

**Không đưa vào hình:** mạng nội bộ chi tiết, ánh xạ cổng, tên volume, biến môi trường,
thứ tự phụ thuộc đầy đủ. Những thứ đó thuộc **phụ lục cài đặt**.

**Chú thích:** *Hình 3.42: Sơ đồ triển khai — một máy chủ vật lý, 15 dịch vụ container
chia tám nhóm.*

---

# PHẦN G — DANH SÁCH KIỂM TRƯỚC KHI NỘP HÌNH

*Bảng G-1: Danh sách kiểm cho từng hình*

| # | Điểm kiểm | Áp cho hình |
|---|---|---|
| 1 | Hình đọc được khi in **trắng đen**, không dùng màu để phân biệt | tất cả |
| 2 | Phần **thiết kế đích** vẽ nét đứt kèm nhãn `«target design»` | 3.15, 3.16, 3.22, 3.23 |
| 3 | Phần **một phần** vẽ kèm nhãn `«partial»` | 3.8, 3.9, 3.22, 3.24 |
| 4 | **Community vẽ NẰM TRONG** cây tổ chức, không phải mặt phẳng ngoài | 3.9, 3.25, 3.32 |
| 5 | Ba bảng `community_*` ghi rõ là **danh mục hệ thống** | 3.25 |
| 6 | **Người ký và tài khoản vận hành là hai cạnh khác nhau** từ bảng mẫu | 3.22, 3.26, 3.38 |
| 7 | **Hai đường thu vẽ tách bạch**, bước trích điểm mốc ở hai chỗ khác nhau | 3.12, 3.13, 3.14, 3.35, 3.36 |
| 8 | **Không vẽ** tiến trình nền làm tác nhân trên sơ đồ use case | 3.12 |
| 9 | **Không vẽ** cung `«include»` tới use case xem nhật ký kiểm toán | 3.8, 3.15 |
| 10 | Khoá ngoại ghép **ghi cặp cột trên cạnh** | 3.24, 3.26, 3.28–3.31 |
| 11 | **Không vẽ** quan hệ từ bản tải lên thô tới mẫu bằng nét liền | 3.16, 3.26 |
| 12 | **Không vẽ** `workspace_members` / `project_members` | 3.24, 3.28 |
| 13 | Mọi vòng lặp có **bộ đếm và giới hạn ghi bằng số** | 3.17, 3.35, 3.39 |
| 14 | Mọi nhánh rẽ có **guard trong ngoặc vuông** | mọi activity diagram |
| 15 | Tên use case trên hình **trùng từng chữ** với bảng danh sách use case | 3.7, 3.8, 3.10, 3.12, 3.15 |
| 16 | Con số trên hình khớp lần đếm cuối trên cơ sở dữ liệu | 3.9, 3.20, 3.23, 3.38 |

**Một lưu ý cuối, quan trọng hơn mười sáu điểm trên:** nếu lược đồ hoặc mã nguồn đổi
sau ngày 18/08/2026, **đếm lại trước khi vẽ**. Một hình mang con số cũ trông giống hệt
một hình mang con số đúng, và đó chính là lý do nó nguy hiểm.
