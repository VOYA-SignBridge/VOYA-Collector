# Từ điển dữ liệu — Nhóm M7: Pháp lý, Kiểm toán & Nền tảng

*10 bảng · 115 cột. Trích từ CSDL đang chạy ngày 18/08/2026.
Quy ước đọc bảng: xem [DD_00_QUY_UOC_VA_MUC_LUC.md](DD_00_QUY_UOC_VA_MUC_LUC.md).*

**Đây là nhóm giữ BẰNG CHỨNG.** Ba nguyên tắc chi phối toàn nhóm:

1. **Văn bản đã công bố là bất biến** — cưỡng chế bằng trigger ở tầng CSDL, không
   bằng kiểm tra ở ứng dụng.
2. **Chấp thuận trỏ tới một cặp (loại, phiên bản) xác định**, không trỏ tới khái
   niệm *"bản hiện hành"*.
3. **Bản ghi lịch sử chép cứng tên tại thời điểm hành động** — cập nhật theo tên
   hiện tại là viết lại lịch sử.

---

## 7.1 Bảng `legal_documents` — Văn bản pháp lý đã công bố

**Khoá chính:** `doc_id` · **Khoá duy nhất:** `(kind, version)` · **RLS:** —
không bật · **Số cột:** 21 · **Số hàng (10/08/2026):** 4

### Nhóm A — Định danh và hiệu lực

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| doc_id | uuid | — | Primary key | Định danh kỹ thuật |
| kind | text | — | Not null, **Unique (kép)**, Check | **Loại văn bản**: điều khoản dịch vụ, chính sách riêng tư… |
| version | text | — | Not null, **Unique (kép)** | **Số hiệu phiên bản** |
| effective_from | timestamptz | — | Not null, Default now() | Ngày bắt đầu có hiệu lực |
| published_at | timestamptz | — | Not null, Default now() | Thời điểm công bố |
| published_by | uuid | — | Null, Foreign key → users.id | Người công bố |
| requires_reconsent | boolean | — | Not null, Default false | **Bản này có buộc chấp thuận lại không** |
| change_summary | text | — | Not null, Default '' | Tóm tắt thay đổi so với bản trước |

### Nhóm B — Nội dung

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| title | text | — | Not null, Default '' | Tiêu đề văn bản |
| body | text | — | Not null, Default '' | **Thân văn bản, lưu TRONG cơ sở dữ liệu** |
| body_format | text | — | Not null, Default 'markdown', Check | Định dạng thân văn bản |
| language | text | — | Not null, Default 'vi' | Ngôn ngữ |
| content_hash | text | — | Not null | **Mã băm nội dung** — cho phép đối chiếu bản đang đọc đúng là bản đã ký |
| byte_size | integer | 32 | Not null, Default 0 | Kích thước nội dung |

### Nhóm C — Tệp đính kèm và lưu trữ

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| url | text | — | Not null | Địa chỉ công khai của văn bản |
| storage_backend | text | — | Not null, Default 'local' | Nơi lưu bản gốc |
| storage_key | text | — | Null | Khoá đối tượng trên kho lưu trữ |
| file_key | text | — | Null, Check | Khoá tệp đính kèm (bản PDF ký, nếu có) |
| file_name | text | — | Null | Tên tệp gốc |
| file_mime | text | — | Null | Kiểu MIME |
| file_size | bigint | 64 | Null | Kích thước tệp |

> ### Bảng này BẤT BIẾN sau khi công bố — cưỡng chế bằng TRIGGER ở tầng CSDL
>
> **Vì sao không kiểm ở ứng dụng:** chấp thuận trỏ tới cặp `(kind, version)`. Nếu
> nội dung sửa được dưới chân bản ghi chấp thuận, **bằng chứng chấp thuận biến
> thành lời khẳng định suông** — người dùng đã đồng ý với một văn bản, và văn bản
> đó nay nói điều khác. Một kiểm tra ở tầng ứng dụng chỉ chặn các đường ghi mà lập
> trình viên nhớ tới; trigger chặn **mọi** đường ghi, kể cả `psql` gõ tay.
>
> **Khoá duy nhất `(kind, version)` là mặt đỡ cho hai khoá ngoại**, từ
> `user_consents` và `signer_consents`. Đây là chỗ hiếm hoi trong lược đồ mà khoá
> ngoại trỏ tới một **khoá duy nhất**, không phải khoá chính — có chủ đích: `doc_id`
> là định danh kỹ thuật, còn `(kind, version)` mới là thứ **có nghĩa nghiệp vụ**.

**`requires_reconsent` tách hai loại thay đổi.** Sửa lỗi chính tả **không** buộc
người dùng chấp thuận lại; đổi phạm vi xử lý dữ liệu **thì có**. Không có cột này,
mọi lần sửa đều buộc chấp thuận lại — và người dùng sẽ bấm đồng ý theo phản xạ,
tức phá đúng giá trị của cơ chế.

**`body` lưu trong CSDL thay vì chỉ lưu tệp** là quyết định về khả năng bảo toàn:
tệp trên đĩa có thể bị thay mà không để lại dấu; hàng trong CSDL có trigger canh.

---

## 7.2 Bảng `legal_document_drafts` — Bản nháp

**Khoá chính:** `draft_id` · **RLS:** — không bật · **Số cột:** 21 · **Số hàng
(10/08/2026):** 1

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| draft_id | uuid | — | Primary key | Định danh bản nháp |
| kind | text | — | Not null, Check | Loại văn bản đang soạn |
| title | text | — | Not null, Default '' | Tiêu đề |
| language | text | — | Not null, Default 'vi' | Ngôn ngữ |
| body | text | — | Not null, Default '' | **Thân văn bản — SỬA ĐƯỢC**, khác hẳn bảng đã công bố |
| body_format | text | — | Not null, Default 'markdown' | Định dạng |
| change_summary | text | — | Not null, Default '' | Tóm tắt thay đổi |
| target_version | text | — | Not null, Default '' | **Số hiệu phiên bản dự kiến** khi công bố |
| requires_reconsent | boolean | — | Not null, Default false | Dự kiến có buộc chấp thuận lại |
| effective_from | timestamptz | — | Null | Ngày hiệu lực dự kiến |
| status | text | — | Not null, Default 'draft', Check | Trạng thái: nháp / đã công bố / đã huỷ |
| revision | integer | 32 | Not null, Default 1, Check | **Số lần sửa bản nháp** |
| based_on_version | text | — | Null | **Bản đang hiệu lực được chép làm điểm xuất phát** |
| published_version | text | — | Null | Phiên bản đã sinh ra từ bản nháp này |
| storage_key | text | — | Null | Khoá đối tượng |
| content_hash | text | — | Null | Mã băm nội dung nháp |
| byte_size | integer | 32 | Not null, Default 0 | Kích thước |
| created_by | uuid | — | Null, Foreign key → users.id | Người soạn |
| updated_by | uuid | — | Null, Foreign key → users.id | Người sửa gần nhất |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm tạo nháp |
| updated_at | timestamptz | — | Not null, Default now() | Lần sửa gần nhất |

**Tách nháp khỏi bản công bố là cách duy nhất để vừa sửa được vừa bất biến được.**
Bản nháp sống ở bảng này, sửa tự do; công bố **sinh ra một hàng mới** ở
`legal_documents`, và từ đó không sửa được nữa.

**`based_on_version` ghi lại điểm xuất phát**, đúng như giao diện mô tả: *"Bản mới
sẽ chép sẵn nội dung bản đang hiệu lực làm điểm xuất phát."* Nó cho phép dựng lại
**cây quan hệ giữa các phiên bản**, không chỉ danh sách phẳng.

---

## 7.3 Bảng `legal_document_events` — Lịch sử vòng đời văn bản

**Khoá chính:** `event_id` · **RLS:** — không bật · **Số cột:** 12 · **Số hàng
(10/08/2026):** 5

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| event_id | bigint | 64 | Primary key, Default nextval(…) | Số thứ tự sự kiện, tăng dần |
| occurred_at | timestamptz | — | Not null, Default now() | Thời điểm xảy ra |
| actor_user_id | uuid | — | Null | Tài khoản thực hiện |
| actor_label | text | — | Not null, Default '' | **Tên người thực hiện TẠI THỜI ĐIỂM ĐÓ**, chép cứng |
| action | text | — | Not null, Check | Hành động: soạn / sửa / công bố / huỷ |
| kind | text | — | Null | Loại văn bản liên quan |
| version | text | — | Null | Phiên bản liên quan |
| draft_id | uuid | — | Null | Bản nháp liên quan |
| revision | integer | 32 | Null | Số lần sửa của nháp tại thời điểm đó |
| storage_key | text | — | Null | Khoá đối tượng tại thời điểm đó |
| content_hash | text | — | Null | **Mã băm nội dung tại thời điểm đó** |
| detail | jsonb | — | Null | Chi tiết bổ sung |

**`actor_user_id` KHÔNG có khoá ngoại tới `users`, và đó là chủ ý** — cùng lý do
với `audit_log`: bản ghi lịch sử phải sống sót sau khi tài khoản bị xoá. Một khoá
ngoại có `ON DELETE CASCADE` sẽ **xoá bằng chứng** cùng với tài khoản; một khoá
ngoại có `RESTRICT` sẽ **chặn việc xoá tài khoản** vĩnh viễn. Bỏ khoá ngoại và chép
cứng `actor_label` là cách thoát khỏi hai lựa chọn đều tệ đó.

---

## 7.4 Bảng `user_consents` — Chấp thuận của tài khoản

**Khoá chính:** `consent_id` · **RLS:** — không bật · **Số cột:** 11 · **Số hàng
(10/08/2026):** 20

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| consent_id | uuid | — | Primary key | Định danh bản ghi chấp thuận |
| user_id | uuid | — | Not null, Foreign key → users.id | Tài khoản chấp thuận |
| kind | text | — | Not null, **Foreign key kép** → legal_documents(kind, version) | Loại văn bản |
| version | text | — | Not null, **Foreign key kép** → legal_documents(kind, version) | **Phiên bản đã chấp thuận** — trỏ tới nội dung xác định |
| accepted_at | timestamptz | — | Not null, Default now() | Thời điểm chấp thuận |
| withdrawn_at | timestamptz | — | Null | Cờ rút lại |
| ip_hash | text | — | Null | **Mã băm địa chỉ IP** lúc chấp thuận — bằng chứng ngữ cảnh, không lộ IP |
| user_agent | text | — | Null | Trình duyệt lúc chấp thuận |
| source | text | — | Not null, Default 'user', Check | **NGƯỜI DÙNG TỰ BẤM hay NGƯỜI VẬN HÀNH GHI HỘ** |
| recorded_by | uuid | — | Null, Foreign key → users.id | Người ghi hộ, nếu có |
| note | text | — | Not null, Default '' | Ghi chú |

> ### Cột `source` là cột trung thực nhất của toàn lược đồ
>
> Nó tách **hai con số trông giống nhau**: số bản ghi chấp thuận tồn tại, và số bản
> ghi **do chính người dùng tạo ra**. Phần chênh lệch là dữ liệu backfill do người
> vận hành ghi hộ.
>
> Giao diện quản trị hiển thị **cả hai cột** và nói thẳng: *"Chênh lệch giữa **Đã
> đồng ý** và **Người dùng tự bấm** là số dòng do người vận hành ghi hộ. **Chúng
> không phải chữ ký.**"*
>
> Không có cột này, một con số *"độ phủ chấp thuận 100 %"* sẽ được đọc thành *"mọi
> người đã đồng ý"* — trong khi thực tế có thể là *"mọi người đã được ghi hộ"*.

**Khoá ngoại ghép `(kind, version)` trỏ tới khoá DUY NHẤT của `legal_documents`,
không phải khoá chính.** Đây là chỗ ghim: bản ghi chấp thuận không thể tồn tại nếu
văn bản tương ứng không tồn tại, và nội dung văn bản đó **không sửa được**.

**`ip_hash` băm thay vì lưu rõ:** đủ để chứng minh hai lần chấp thuận đến từ cùng
một địa chỉ, **không đủ** để biết địa chỉ đó là gì.

---

## 7.5 Bảng `signer_consents` — Đồng thuận của người ký

**Khoá chính:** `consent_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 11 · **Số
hàng (10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| consent_id | uuid | — | Primary key | Định danh bản ghi đồng thuận |
| tenant_id | text | — | Not null, Foreign key → tenants.tenant_id | Tổ chức |
| signer_id | text | — | Not null, **Foreign key kép** → signers(tenant_id, signer_id) | **NGƯỜI KÝ — chủ thể dữ liệu** |
| scope | text | — | Not null, Check | **MỨC ĐỒNG THUẬN** — thang ba mức, quyết định dữ liệu được phát hành tới đâu |
| kind | text | — | Not null, **Foreign key kép** → legal_documents(kind, version) | Loại văn bản |
| version | text | — | Not null, **Foreign key kép** → legal_documents(kind, version) | Phiên bản đã đồng thuận |
| granted_at | timestamptz | — | Not null, Default now() | Thời điểm đồng thuận |
| withdrawn_at | timestamptz | — | Null, Check | **Thời điểm RÚT** — rỗng nghĩa là còn hiệu lực |
| guardian_name | text | — | Null | **Tên người giám hộ**, khi chủ thể là trẻ vị thành niên |
| evidence | text | — | Null | Bằng chứng đồng thuận (biểu mẫu giấy đã ký, ghi âm…) |
| recorded_by | uuid | — | Null, Foreign key → users.id | Người ghi nhận |

**Ràng buộc `CHECK` trên cặp `(withdrawn_at, granted_at)`:** thời điểm rút không
được **trước** thời điểm đồng thuận.

> ### `user_consents` và `signer_consents` là HAI BẢNG KHÁC NHAU, không phải hai dòng của cùng một bảng
>
> | | `user_consents` | `signer_consents` |
> |---|---|---|
> | Chủ thể | **Tài khoản** chấp thuận điều khoản dịch vụ | **Chủ thể dữ liệu** cho phép dùng dữ liệu của mình |
> | Có `tenant_id` | Không | **Có**, và bật RLS |
> | Có mức đồng thuận | Không (nhị phân) | **Có** — thang ba mức |
> | Chi phối đường phát hành dữ liệu | **Không** | **CÓ** |
>
> **Chỉ vế thứ hai chi phối đường phát hành dữ liệu.** Một tài khoản đã chấp thuận
> điều khoản dịch vụ **không** có nghĩa người ký trong dữ liệu của họ đã cho phép
> dùng dữ liệu đó cho nghiên cứu.

**`scope` là cột được đọc ở CỔNG THỨ NHẤT của quy trình huấn luyện**, áp **lúc
chọn mẫu**: mẫu không đủ mức **không xuất hiện** trong bản phát hành.

**`guardian_name` tồn tại vì chủ thể dữ liệu có thể là trẻ em.** Một hệ thống thu
ngôn ngữ ký hiệu chạm tới người học ở mọi lứa tuổi, và đồng thuận của trẻ vị thành
niên cần người giám hộ.

**Số hàng 0 là số liệu phải báo cáo.** Cơ chế đã cài đặt đầy đủ — bảng, thang mức,
cổng chặn, giao diện ký và rút ở `/settings/consents`. Cái còn thiếu là **dữ liệu**:
chưa có bản ghi đồng thuận nào của người ký. Đây là chặn dữ liệu, **không phải chặn
mã**.

---

## 7.6 Bảng `audit_log` — Nhật ký kiểm toán

**Khoá chính:** `audit_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 10 · **Số hàng
(10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| audit_id | bigint | 64 | Primary key, Default nextval(…) | Số thứ tự bản ghi, tăng dần |
| tenant_id | text | — | Null, Foreign key → tenants.tenant_id | Tổ chức; **rỗng với hành động cấp nền tảng** |
| actor_user_id | uuid | — | Null, Foreign key → users.id | Tài khoản thực hiện |
| actor_label | text | — | Null | **TÊN NGƯỜI THỰC HIỆN TẠI THỜI ĐIỂM HÀNH ĐỘNG** — không cập nhật theo tên hiện tại |
| action | text | — | Not null, Check | Hành động đã thực hiện |
| target_type | text | — | Null | Loại đối tượng bị tác động |
| target_id | text | — | Null | Định danh đối tượng bị tác động |
| detail | jsonb | — | Null | Chi tiết bổ sung |
| ip_hash | text | — | Null | Mã băm địa chỉ IP |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm ghi |

> ### `actor_label` là bằng chứng lịch sử — cột KHÔNG được cập nhật
>
> Khi một tài khoản đổi tên, **năm chỗ khác** trong hệ thống được cập nhật theo —
> nhưng cột này thì **không**, có chủ đích: một bản ghi kiểm toán phải nói ra tên
> **tại thời điểm hành động xảy ra**. Cập nhật nó theo tên hiện tại là **viết lại
> lịch sử**.
>
> Giao diện tài khoản nói thẳng điều này với người dùng: *"Nhật ký kiểm toán giữ
> nguyên tên cũ — đó là bằng chứng lịch sử về việc ai đã làm gì, và sửa nó theo tên
> mới là viết lại lịch sử."*

**Ghi nhật ký FAIL-CLOSED khi thiếu phạm vi:** không có ngữ cảnh thì **từ chối
ghi**, thay vì ghi một dòng không quy được về đâu. Cột `tenant_id` cho phép rỗng
chỉ vì hành động **cấp nền tảng** thật sự không thuộc tổ chức nào — đó là một trạng
thái hợp lệ, không phải một lối thoát.

**Nhật ký ghi ở HAI nơi:** Redis (đường nhanh, đọc trong ứng dụng) và bảng này
(**bản bền**). `plans.audit_retention_days` quyết định giữ bao lâu.

**Số hàng 0 tại ảnh chụp 10/08/2026** — con số này **đã thay đổi đáng kể** kể từ
đó, theo ghi chú ở Phụ lục A.

---

## 7.7 Bảng `platform_settings` — Cấu hình nền tảng

**Khoá chính:** `key` · **RLS:** — không bật · **Số cột:** 4 · **Số hàng
(10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| key | text | — | Primary key | Tên tham số cấu hình |
| value | text | — | Not null | Giá trị, lưu dạng chuỗi |
| updated_by | uuid | — | Null, Foreign key → users.id | Người sửa gần nhất |
| updated_at | timestamptz | — | Not null, Default now() | Lần sửa gần nhất |

**Mô hình khoá–giá trị: thêm tham số mới không cần đổi lược đồ.** Đánh đổi: **không
kiểm được kiểu ở tầng CSDL** — mọi giá trị là chuỗi, và việc diễn giải do ứng dụng
làm.

**Cấu hình ở đây áp cho MỌI tổ chức** (ví dụ: kênh tin nhắn có bật không). Đó là lý
do nghiệp vụ *"quản trị người dùng và chính sách"* tách khỏi *"tổ chức và đăng ký
dịch vụ"*: sai ở đây là sai cho tất cả.

---

## 7.8 Bảng `sot_authorized_keys` — Khoá ký được tin cậy

**Khoá chính:** `public_key` · **RLS:** — không bật · **Số cột:** 7 · **Số hàng
(10/08/2026):** 0

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| public_key | text | — | Primary key | **Khoá công khai Ed25519** của một máy ghi nguồn sự thật |
| name | text | — | Not null, Unique | **Tên máy** — giá trị trả về khi xác minh thành công |
| fingerprint | text | — | Not null | Vân tay khoá, để đối chiếu bằng mắt |
| note | text | — | Null | Ghi chú |
| added_by | text | — | Null | Người đăng ký máy |
| added_at | timestamptz | — | Not null, Default now() | Thời điểm đăng ký |
| revoked_at | timestamptz | — | Null | **Thời điểm thu hồi quyền ghi của máy đó** |

> ### Bảng này cài đặt vế thứ ba của hợp đồng xác minh
>
> ```
> Tạo tác hợp lệ = Toàn vẹn ∧ Chữ ký hợp lệ ∧ NGƯỜI KÝ ĐƯỢC TIN CẬY ∧ Chính sách phiên bản hợp lệ
> ```
>
> **Vế thứ ba là chỗ dễ bỏ sót nhất.** Kẻ tấn công dựng dữ liệu khác, tính mã băm
> đúng, viết bản kê đúng, rồi **tự ký bằng khoá của hắn**. Chữ ký ấy **hợp lệ về
> mật mã**. Nếu hệ thống chỉ hỏi *"chữ ký có hợp lệ không"* mà không hỏi *"hợp lệ
> theo khoá NÀO"* thì toàn vẹn đúng nhưng **thẩm quyền sai**.
>
> **Cột `name` là lý do hàm xác minh trả về TÊN KHOÁ thay vì một giá trị đúng/sai.**
> "Ai ký" là **một phần của kết quả xác minh**, không phải một chi tiết phụ. Giao
> diện hiển thị đúng như vậy: huy hiệu **`signed: {tên khoá}`**, hoặc **"chữ ký lạ"**.

**Thẩm quyền ký gắn với MÁY, không gắn với người.** Chỉ máy có khoá riêng mới là
*"Máy ghi"*; mọi máy khác chỉ có khoá công khai để xác minh, và là *"Read-only"*.

**Khoá trong bảng này được HỢP NHẤT với bộ khoá cam kết trong mã nguồn.** Bảng cho
phép thêm máy lúc chạy; mã nguồn giữ bộ khoá nền tảng không xoá được bằng một câu
lệnh SQL.

---

## 7.9 Bảng `google_sheets_sync_status` — Trạng thái phản chiếu bảng tính

**Khoá chính:** `id` · **RLS:** — không bật · **Số cột:** 7 · **Số hàng
(10/08/2026):** 1

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| id | integer | 32 | Primary key, Default nextval(…) | Số thứ tự |
| table_name | varchar | 50 | Not null, Unique | **Bảng nguồn** đang được phản chiếu |
| current_spreadsheet_id | varchar | 100 | Not null, Default '' | Bảng tính đích hiện tại |
| current_sheet_index | integer | 32 | Not null, Default 1 | **Trang thứ mấy** trong bảng tính |
| current_data_rows | integer | 32 | Not null, Default 0 | Số hàng dữ liệu đã ghi ở trang hiện tại |
| max_rows_per_sheet | integer | 32 | Not null, Default 500000 | **Trần số hàng mỗi trang** — chạm trần thì sang trang mới |
| updated_at | timestamptz | — | Null, Default now() | Lần đồng bộ gần nhất |

**Ba cột `current_sheet_index` + `current_data_rows` + `max_rows_per_sheet` cài
đặt cơ chế tràn trang.** Bảng tính ngoài có giới hạn số ô; khi chạm trần, tiến
trình chuyển sang trang mới thay vì dừng. Không có ba cột này, việc đồng bộ sẽ hỏng
**âm thầm** ở một ngưỡng không ai đoán trước được.

**Bản phản chiếu GIỮ LẠI dòng đã xoá mềm** kèm dấu `deleted_at`, và **không dịch
dòng**. Dịch dòng làm mọi tham chiếu theo số hàng sai — mà số hàng chính là thứ
người đối soát dùng để tra.

---

## 7.10 Bảng `event_outbox` — Hộp thư đi sự kiện

**Khoá chính:** `event_id` · **RLS:** ✔ bật, ✔ FORCE · **Số cột:** 11

| Field Name | Data type | Field Length | Constraint | Description |
|---|---|---|---|---|
| event_id | uuid | — | Primary key, Default gen_random_uuid() | Định danh sự kiện |
| tenant_id | text | — | Null, Foreign key → tenants.tenant_id | Tổ chức; rỗng với sự kiện cấp nền tảng |
| event_type_code | text | — | Not null, Check | Loại sự kiện |
| payload | jsonb | — | Not null, Default '{}' | **Tải trọng sự kiện**, lưu nguyên khối |
| occurred_at | timestamptz | — | Not null, Default now() | **Thời điểm sự kiện XẢY RA** trong nghiệp vụ |
| created_at | timestamptz | — | Not null, Default now() | Thời điểm ghi vào hộp thư |
| dispatch_status | text | — | Not null, Default 'PENDING', Check | Trạng thái gửi |
| attempts | integer | 32 | Not null, Default 0, Check | Số lần đã thử gửi |
| available_at | timestamptz | — | Not null, Default now() | **Thời điểm được phép thử lại** — lùi dần theo cấp số |
| processed_at | timestamptz | — | Null | Thời điểm gửi xong |
| last_error | text | — | Null | Lỗi của lần thử gần nhất |

> ### Đây là mẫu thiết kế "hộp thư đi giao dịch" (transactional outbox)
>
> Sự kiện được ghi vào bảng này **TRONG CÙNG GIAO DỊCH** với thay đổi dữ liệu
> nghiệp vụ. Nhờ đó **không tồn tại** trạng thái *"dữ liệu đã đổi nhưng sự kiện
> chưa được ghi nhận"* — thứ không sửa được về sau vì **không ai biết nó đã xảy
> ra**. Tiến trình nền đọc hộp thư và gửi đi sau, tách khỏi giao dịch gốc.

**Hai cột thời gian `occurred_at` và `created_at` KHÁC NHAU, và phân biệt này có
giá trị:** cái đầu là *"chuyện xảy ra lúc nào"*, cái sau là *"ta ghi nhận lúc
nào"*. Chúng lệch nhau khi sự kiện được ghi bù. Bên nhận cần cái đầu để sắp thứ tự
đúng.

---

## Tổng kết nhóm M7

```
legal_documents (kind, version) ──< user_consents      [KHOÁ NGOẠI GHÉP tới khoá DUY NHẤT]
legal_documents (kind, version) ──< signer_consents    [KHOÁ NGOẠI GHÉP]
legal_document_drafts ──(công bố)──> legal_documents   [nháp sửa được → bản bất biến]
legal_document_events                                  [lịch sử, KHÔNG có khoá ngoại tới users]
signers (1) ──< signer_consents                        [KHOÁ NGOẠI GHÉP]
tenants (1) ──< audit_log · event_outbox
audit_log                                              [actor_label chép cứng]
```

| Đặc điểm | Giá trị |
|---|:--:|
| Bảng có `tenant_id` | 3 |
| Bảng bật RLS + FORCE | **3** (`signer_consents`, `audit_log`, `event_outbox`) |
| Bảng **không** RLS | 7 — đều là dữ liệu **cấp nền tảng**, không thuộc tổ chức nào |
| Khoá ngoại ghép trong nhóm | 3 |
| Bảng bất biến cưỡng chế bằng trigger | 1 (`legal_documents`) |
| Cột chép cứng tên lịch sử | 2 (`audit_log.actor_label`, `legal_document_events.actor_label`) |

### Ba cột mà cả hệ thống dựa vào để nói *"chuyện này đã xảy ra thật"*

| Cột | Bảng | Bảo vệ điều gì |
|---|---|---|
| `content_hash` | `legal_documents` | Nội dung người dùng đã đồng ý **đúng là nội dung này** |
| `source` | `user_consents` | Chấp thuận **do người dùng tự bấm**, không phải ghi hộ |
| `actor_label` | `audit_log` | Người thực hiện **mang tên tại thời điểm đó** |

Ba cột này nhỏ, nhưng bỏ bất kỳ cột nào cũng biến một hệ thống có bằng chứng thành
một hệ thống chỉ có **lời khẳng định**.
