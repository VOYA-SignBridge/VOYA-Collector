# Mười cặp khái niệm bị gộp — và ranh giới thật giữa chúng

*Dựng 2026-08-10. Mỗi mục trả lời ba câu: **gộp cái gì**, **ranh giới nằm ở
đâu trong mã**, và **hỏng thế nào nếu gộp**.*

Tài liệu này không phải từ điển thuật ngữ. Nó là danh sách những chỗ mà hai thứ
khác nhau đang dùng chung một cái tên, và mỗi chỗ như vậy vừa là nơi sinh lỗi,
vừa là câu hỏi mà người đọc kỹ sẽ đặt ra.

---

## 1. Quản trị viên hệ thống ≠ quản trị viên tổ chức

| | Quản trị viên **nền tảng** | Quản trị viên **tổ chức** |
|---|---|---|
| Kiểm bằng | `require_admin` (`users.is_admin`) | `require_tenant_admin` (`tenant_members.role = 'admin'`) |
| Làm được | tạo/xoá tenant, gắn tài khoản vào tenant, xoá sạch dữ liệu | mời, đổi vai, xem, xuất dữ liệu của **tổ chức mình** |
| Giao diện | 9 trang `/admin/*` | `/organization` |

**Ranh giới có lý do cụ thể.** `add_member` gắn một tài khoản **theo id**, và id
tài khoản không phải bí mật. Nếu quản trị viên tổ chức làm được việc đó, họ kéo
được bất kỳ ai trên hệ thống vào tổ chức của mình. Đường đưa người vào dành cho
họ là **lời mời**, thứ đòi hỏi chính người kia phải hành động.

Hai vòng quyền này đã tách rành mạch ở backend từ v4. Cái từng thiếu là **mặt
giao diện của vòng thứ hai** — mọi endpoint tổ chức chỉ gọi được bằng `curl`
cho tới 2026-08-10.

---

## 2. Đình chỉ ≠ khoá ≠ xoá

Lược đồ có **hai cột** nhưng chỉ **một bậc tự do**:

```sql
is_active     boolean
suspended_at  timestamptz   -- ghi ở đúng MỘT chỗ, và ghi như thế này:
                            -- suspended_at = CASE WHEN %s THEN NOW() ELSE NULL END
```

`suspended_at` là *dấu thời gian của lần cờ boolean lật*, không phải một trạng
thái độc lập. Nên lược đồ vẫn **không biểu diễn được ba trạng thái**:

| Muốn nói | Nghĩa | Biểu diễn được? |
|---|---|---|
| Đình chỉ | ngừng ghi, còn đọc, dữ liệu nguyên vẹn | qua `billing_status='suspended'` — xem §7 |
| Khoá | không vào được | không |
| Xoá | xoá mềm, chờ hết ân hạn rồi xoá thật | có (`deleted_at` + `tenant_purges`) |

Chỗ *thật sự* diễn tả được "ngừng ghi, còn đọc" là `tenants.billing_status`, và
đó là một trục khác — trục thương mại, không phải trục quản trị.

---

## 3. Xoá mềm ≠ thùng rác ≠ xoá vĩnh viễn

Ba mức đều có trong mã, và **người dùng chưa từng được giải thích**:

| Mức | Chuyện gì xảy ra | Hoàn tác được? |
|---|---|---|
| Xoá mềm | `deleted_at` được ghi; hàng biến khỏi mọi truy vấn thường | có |
| Thùng rác | hàng đã xoá mềm, hiện ra ở `/trash` để chủ nhân xem lại | có |
| Xoá vĩnh viễn | tệp rời khỏi ổ đĩa và hàng rời khỏi bảng | **không** |

Ranh giới quan trọng nhất: **xoá mềm không đụng tới tệp**. Một người nghĩ mình
đã xoá dữ liệu khỏi hệ thống trong khi tệp vẫn nằm nguyên là một hiểu nhầm về
quyền riêng tư, không phải một chi tiết giao diện.

---

## 4. Tài khoản thu dữ liệu ≠ người ký

Đây là cặp nặng nhất, vì nó quyết định ai có quyền với dữ liệu nào.

| | `auth_user_id` | `signer_id` |
|---|---|---|
| Là ai | tài khoản đã bấm nút thu | người có **bàn tay** trong dữ liệu |
| Chủ thể dữ liệu? | không | **có** |
| Phủ (10/08/2026) | 95,7% mẫu, 3 giá trị phân biệt | 43,4% mẫu, 4 giá trị phân biệt |

Trong luồng hiện tại hai danh tính thường trùng nhau — đường quay trực tiếp suy
người ký từ chính tài khoản đang đăng nhập. Nhưng lược đồ **phải** giữ chúng
tách rời, vì có trường hợp không trùng: thu hộ tại cơ sở giáo dục đặc biệt,
người giám hộ ký thay.

Hệ quả đo được của việc thiếu quy kết: **56,6% kho dữ liệu không truy được về
người có bàn tay trong đó.** Nếu một người nói "tôi rút phần đóng góp của tôi",
hệ thống không xác định nổi đó là những dòng nào.

**Không lùi từ `signer_id` về `user_id`.** `user_id` là văn bản tự do và đã từng
gộp nhầm người: "Trâm"/"Tram" là một, "Trân" thì không.

---

## 5. Bốn nghĩa của "thu hồi"

`docs/needFix/COMMUNITY_DATA_COMMONS.md` tách đúng bốn nghĩa. Cổng đồng thuận
(`app/consent_gate.py`) chỉ thi hành **nghĩa thứ hai**:

| # | Nghĩa | Đã thi hành? |
|---|---|---|
| 1 | Thu hồi quyền truy cập của một người | có (RLS + vai) |
| 2 | Gỡ khỏi bản phát hành **mới** | **có** — bốn đường dữ liệu đều qua cổng |
| 3 | Xoá khỏi lưu trữ | **không** — thao tác vận hành, làm tay |
| 4 | Thu hồi giấy phép **đã cấp** cho bên thứ ba | không — cần cơ chế pháp lý, không phải phần mềm |

Hứa "xoá là biến mất hoàn toàn" là hứa nghĩa 3 và 4 trong khi chỉ làm nghĩa 2.
Giao diện rút đồng thuận nói thẳng điều này, và có test ghim câu chữ.

---

## 6. Hạn mức đang dùng ≠ đã từng dùng

| | Dùng để | Nguồn |
|---|---|---|
| Đang dùng | **chặn** — còn thêm được không | đếm trực tiếp từ bảng nguồn (`plans.USAGE_METRICS`) |
| Đã từng dùng | **tính tiền** — tháng này đã tiêu bao nhiêu | `tenant_usage_daily`, gộp mỗi giờ |

Gộp hai thứ này là cách chắc chắn để một ngày nào đó biểu đồ nói 900 còn bộ
chặn nói 1200 trên cùng một tenant. Chúng cố ý đọc từ hai nguồn khác nhau, và
điều đó là **đúng**, không phải trùng lặp cần dọn.

Chi tiết đáng nhớ: `current_usage` **fail-OPEN** (trả 0 khi truy vấn hỏng),
ngược với phần còn lại của module. Lý do: chỉ số này nằm ở đường ghi nóng, và
biến một sự cố cơ sở dữ liệu thành "mọi người hết hạn mức" là nhân sự cố lên.
Ranh giới thật — ai đọc được dữ liệu nào — nằm ở RLS, không ở đây.

---

## 7. Trạng thái thương mại ≠ trạng thái quản trị

`tenants.billing_status` và `tenants.is_active` là **hai trục khác nhau**, và
lẫn chúng là lý do §2 khó nói cho rõ.

| `billing_status` | Ghi được? |
|---|---|
| `trialing`, `active` | có |
| `past_due` | **có** — có chủ ý |
| `suspended` | không (chỉ đọc) |
| `cancelled` | không |

**`past_due` vẫn ghi được** là một quyết định, không phải sơ suất: khoá dữ liệu
của một trường vì hoá đơn trễ hai ngày là cách nhanh nhất để mất họ, và số tiền
không vì thế mà đòi được nhanh hơn.

Xem `docs/SUBSCRIPTION_LIFECYCLE.md`.

---

## 8. Đã đăng ký ≠ huấn luyện được

Một lớp từ vựng nằm trong danh mục **không** đồng nghĩa với việc nó có đủ dữ
liệu để huấn luyện. Hai câu hỏi khác nhau:

- *đã đăng ký* — có mã, có nhãn, có phiên bản trong danh mục
- *huấn luyện được* — có đủ mẫu, đủ chất lượng, và **đủ đồng thuận**

Vế thứ ba mới thêm vào năm 2026-08-09: một lớp có 500 mẫu mà người ký chưa đồng
ý mức tương ứng thì với đường phát hành nghiên cứu nó là lớp **rỗng**.

---

## 9. Ba mặt phẳng dữ liệu

| Mặt phẳng | Là gì | Ai sở hữu |
|---|---|---|
| **System Catalog** | cấu hình nền tảng: ngôn ngữ, phương ngữ, hồ sơ nhận dạng | nền tảng |
| **Community Commons** | dữ liệu do người dùng đóng góp cho cộng đồng | người đóng góp giữ quyền, cấp phép cho nền tảng |
| **Dữ liệu tenant** | dữ liệu riêng của một tổ chức | tổ chức đó |

Nguyên tắc mà `COMMUNITY_DATA_COMMONS.md` đặt ra và cần giữ nguyên trong quyển:
**quyền quản trị hạ tầng không đồng nghĩa quyền khai thác dữ liệu.** Người vận
hành máy chủ không vì thế mà có quyền công bố dữ liệu của người đóng góp.

---

## 10. Bản nháp ≠ đã công bố ≠ cần đồng thuận lại

| Trạng thái | Ai thấy | Ràng buộc |
|---|---|---|
| `draft` / `in_review` / `approved` | chỉ người soạn | sửa được thoải mái |
| đã công bố | mọi người | **thân văn bản bất biến** (trigger ở CSDL) |
| `requires_reconsent` | mọi người | mọi chấp thuận cũ **mất hiệu lực** |

`requires_reconsent` tách hai loại thay đổi: sửa lỗi chính tả thì không nên đá
mọi người ra màn hình đồng ý; đổi phạm vi xử lý dữ liệu thì phải.

Một chấp thuận trỏ tới `(kind, version)`. Đổi nội dung dưới chân nó biến bằng
chứng thành lời khẳng định suông — bản ghi nói người ta đồng ý bản 2026-08-07,
nhưng bản 2026-08-07 giờ nói điều khác. Đó là lý do trigger bất biến tồn tại.

---

## 11. Người chạy huấn luyện ≠ tổ chức sở hữu kết quả

`training_jobs` mang cả `tenant_id` lẫn người phái. Chúng trả lời hai câu:

- **ai bấm nút** — để kiểm toán và để tính vào hạn mức của ai
- **kết quả thuộc về ai** — checkpoint, số đo, và quyền dùng lại

Một quản trị viên nền tảng chạy một lượt huấn luyện cho tổ chức X thì người
chạy là nền tảng, còn kết quả thuộc X. Gộp hai cái làm một là hoặc tính nhầm
hạn mức, hoặc trao kết quả cho nhầm người.

---

## Vì sao tài liệu này tồn tại

Mỗi cặp ở trên đã từng — hoặc đang — gây ra một lỗi thật hoặc một hiểu nhầm
thật. Danh sách này không phải bài tập phân loại: nó là bản đồ những chỗ mà đọc
lướt sẽ đọc sai.
