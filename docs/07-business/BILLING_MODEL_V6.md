# Mô hình billing v6 — Free / Plus / Pro / Enterprise

*Chốt hướng 2026-08-13. Thay thế mô hình `internal / trial / school / institution`
mô tả ở `docs/07-business/SUBSCRIPTION_LIFECYCLE.md` §10 và `KNOWN_ISSUES.md`.*

Tài liệu này là **nguồn sự thật của thiết kế**, viết TRƯỚC khi có mã. Lý do nằm ở
mục 0: một lượt migration đã áp dụng thì không sửa lại được.

---

## 0. Ràng buộc chi phối mọi thứ dưới đây

`app/storage/schema_version.py` băm phần **một chiều** của migration và ghi
checksum vào `schema_migrations`. Sau khi v6 chạy trên một cơ sở dữ liệu, sửa nội
dung v6 sẽ làm backend **từ chối khởi động** trên chính máy đó. Đường sửa duy nhất
là tạo v7.

Hệ quả thực tế cho kế hoạch 15 bước:

* Mỗi bước có đổi hình dạng bảng phải là **một phiên bản lược đồ riêng** (v6, v7,
  v8…), không gộp dần vào một v6 sửa nhiều lần.
* Thứ tự các bước = thứ tự các phiên bản. Đảo bước sau khi đã deploy = một phiên
  bản nữa.
* Phần thuần THÊM (`ADD COLUMN IF NOT EXISTS`, `CREATE TABLE IF NOT EXISTS`) chạy
  được ở `ensure_tables()` và **không** vào checksum — dùng nó tối đa để giảm số
  câu một chiều.

Vì vậy bảng dưới đây gộp các bước của kế hoạch thành **4 phiên bản lược đồ**, chứ
không phải 15.

| Phiên bản | Gồm bước | Nội dung một chiều |
|---|---|---|
| **v6** | 1 | Đổi mã gói, `billing_exempt`, cột hạn mức mới, giá nullable |
| **v7** | 2 + 3 + 4 | Bỏ `max_seats/max_samples/max_classes`, enforce storage, quota workspace/project |
| **v8** | 5 + 6 + 7 | Training credits + ledger, bỏ `training_seconds`/`max_training_jobs_per_month`, `price_cents` → `price_minor_units`, bỏ `quarterly` |
| **v9** | 8 + 9 | `billing_customers`, `subscriptions`, `invoices`, `invoice_items`, `payments`, `billing_webhook_events` |

Bước 10–15 là mã ứng dụng, không cần phiên bản lược đồ mới.

---

## 1. Bốn gói

`plan_code` là mã ổn định, `display_name` chỉ để hiển thị.

| | `free` | `plus` | `pro` | `enterprise` |
|---|---|---|---|---|
| Thành viên | ∞ | ∞ | ∞ | ∞ |
| Workspace | 1 | 5 | 20 | NULL (custom) |
| Project | 5 | 25 | 100 | NULL |
| Storage | 5 GB | 50 GB | 250 GB | NULL |
| Sample / Class | ∞ | ∞ | ∞ | ∞ |
| Training credits / kỳ | 60 | 250 | 1 000 | NULL |
| Training đồng thời | 1 | 2 | 4 | NULL |
| Audit retention | 7 ngày | 30 ngày | 180 ngày | NULL (∞) |
| API key | 0 | 3 | 25 | NULL |
| Webhook | 0 | 2 | 10 | NULL |
| Visibility / Share / Fork / Provenance | ✓ | ✓ | ✓ | ✓ |
| Giá | 0 | chưa công bố | chưa công bố | theo hợp đồng |

`NULL` = **không giới hạn**, quy ước đã có từ v4 và không đổi. Mọi con số là
**seed**, sửa được lúc chạy qua `PATCH /billing/plans/{code}` — không hằng số nào
trong mã được phép nhắc lại chúng.

### `free` là gói vĩnh viễn

```
billing_period    = 'none'
current_period_end = NULL
price             = 0
trial_ends_at     → không dùng nữa
```

Không có "hết hạn dùng thử". Đây là điểm khác biệt lớn nhất so với mô hình cũ, và
là lý do **không sửa lỗi trial-vô-hạn**: hành vi đó trở thành hành vi đúng, chỉ
thiếu một cái tên đúng.

### `internal` biến mất khỏi bảng giá

Tenant nền tảng không được giả lập bằng một gói thương mại. Thay bằng thuộc tính
trên tenant:

```sql
ALTER TABLE tenants ADD COLUMN billing_exempt BOOLEAN NOT NULL DEFAULT FALSE;
```

`billing_exempt = TRUE` → `plans.enforce()` thoát sớm, không kiểm gì. Tenant gốc
được đặt cờ này.

**Quyết định kỹ thuật:** gói `internal` được **đổi tên** thành `enterprise` chứ
không bị xoá. Lý do: `tenants.plan_code` và `tenant_subscriptions.plan_code` đều
có khoá ngoại `ON UPDATE CASCADE` trỏ vào `plans.plan_code`, nên đổi tên tự lan
sang lịch sử, còn `DELETE` sẽ bị `RESTRICT` chặn vì có dòng đăng ký cũ tham chiếu.
Hạn mức của `internal` vốn đã là NULL toàn phần — đúng nghĩa "custom" của
Enterprise. Sau lượt đổi tên, **không còn gói nào tên `internal`**, đúng yêu cầu.

Ánh xạ đầy đủ của v6:

```
internal    → enterprise   (giữ nguyên hạn mức NULL)
trial       → free
school      → plus
institution → pro
```

Cả bốn là `UPDATE plans SET plan_code = …`, cascade tự lo phần còn lại.

---

## 2. Membership không phải billing quota

`max_seats` bị **loại khỏi `plans`**. Số thành viên không giới hạn ở mọi gói, kể
cả `free`.

Membership thuộc mặt phẳng phân quyền (`memberships`, view `tenant_members`), và
nó ở đó vì lý do bảo mật chứ không vì lý do thương mại. Một người thuộc 20 project
vẫn là một membership của tenant.

Chỗ phải gỡ: `tenant_admin.py:699` (`check_quota(tenant_id, "seats", adding=1)`)
và mục `seats` trong `plans.USAGE_METRICS`.

---

## 3. Storage là quota ràng buộc duy nhất của dữ liệu

Bỏ `max_samples` và `max_classes`. Hai quota chồng lên cùng một tài nguyên là hai
cách nói khác nhau về một giới hạn, và người dùng không đoán được cái nào chặn
mình.

Nguyên tắc: **tạo bao nhiêu sample tuỳ ý, miễn tổng dung lượng còn trong quota.**

Khi chạm trần storage:

| Hành động | Free đã đầy 5 GB |
|---|---|
| upload tệp mới, tạo raw upload, sinh artifact lớn | ✗ chặn |
| đọc, tải về, export, xoá, sửa metadata | ✓ chạy |

**Không suspend tenant vì đầy đĩa.** `suspended` chỉ còn là quyết định của người
vận hành (lạm dụng, vi phạm), không phải hệ quả của một hạn mức.

### Enforce ở đường ghi, không đợi rollup

Đây là điểm số 2 của bản audit, và nó phải sửa thật:

```
current_storage_bytes + incoming_size <= effective_storage_limit
```

kiểm **trước khi nhận tệp**, không đợi `tenant_usage_daily` hôm sau.

Vấn đề: `plans.py` cố ý đếm mọi chỉ số bằng `count(*)` trên bảng nguồn để không có
bản sao nào lệch được. Storage không theo được nguyên tắc đó — `usage.tenant_storage_mb()`
đi bộ cả cây thư mục, mất hàng giây, không thể chạy ở mỗi lượt upload.

Nên storage là **ngoại lệ có kiểm chứng**, đúng như `plans.py` đã dự liệu ở
docstring đầu tệp ("chỗ sửa là thêm một bộ đếm có đối chiếu định kỳ"):

* một bộ đếm bền `tenant_storage.bytes_used`, cộng/trừ ở mọi đường ghi và xoá tệp;
* lượt đi bộ hằng ngày **đối chiếu** và ghi đè bộ đếm nếu lệch, kèm log mức WARNING;
* `tenant_usage_daily.storage_mb` giữ nguyên vai trò analytics.

Pre-check dùng `Content-Length`; sau khi ghi xong thì cộng kích thước **thật** vào
bộ đếm. Một tệp khai gian `Content-Length` chỉ vượt được đúng một lần rồi bộ đếm
thật chặn lượt sau — chấp nhận được, cùng lý do với `adding=1` ở
[upload.py:101-107](../../backend/app/routers/upload.py#L101-L107).

---

## 4. Training: credits thay vì thời gian

Bỏ khỏi gói thương mại: `training_seconds`, giới hạn phút/job, giờ/tháng,
`max_training_jobs_per_month`.

**Training Credit (TC)** = đơn vị compute chuẩn hoá, ước lượng trước khi chạy:

```
estimated_tc = f(dataset workload, model complexity, training config, compute profile)
```

Điều kiện khởi động một job:

```
estimated_tc <= available_tc   AND   running_jobs < concurrent_limit
```

Không giới hạn **số lần** train một cách nhân tạo: 60 TC là 30 job nhỏ, hoặc 4 job
nặng — người dùng tự chọn.

### Concurrency vẫn giới hạn

Đây không phải giới hạn thời gian mà là bảo vệ scheduler GPU. Free 1, Plus 2, Pro 4.
Job thứ hai của Free vào `queued`, không bị từ chối. Safety timeout kỹ thuật để
giết job treo vẫn tồn tại nhưng **không phải quyền lợi của gói** và không được đem
lên bảng giá.

### Ledger, không phải một con số

```
training_credit_ledger(
  entry_id, tenant_id, training_job_id, entry_type,
  credits, reason, created_at
)
```

```
+60   monthly allocation
 -5   training job #A
-12   training job #B
+12   infrastructure failure refund
+100  purchased credit pack
```

Số dư là `sum(credits)`, không phải một cột bị ghi đè. Lý do giống hệt lý do
`plans.py` không nuôi bộ đếm sample: một con số bị ghi đè không tự lộ ra khi nó
sai, và ở đây "sai" nghĩa là tính tiền sai.

### Vòng đời khác nhau giữa hai quota

| | reset theo kỳ? |
|---|---|
| Storage (dung lượng) | **không** — là sức chứa |
| Included TC | **có** — hết kỳ cấp lại |

Free cũng reset: tháng 8 còn 20 TC, sang tháng 9 là **60**, không phải 80.

---

## 5. Entitlement = gói + phần mua thêm

Quota thực tế không đọc thẳng từ `plans`:

```
effective_storage = plan_storage
                  + purchased_storage
                  + promotional_storage
                  + admin_adjustment

available_tc      = included_remaining
                  + purchased_remaining
                  + granted_remaining
```

Free không có add-on: hết quota thì đề nghị nâng Plus.

Điều này nghĩa là **mọi chỗ hỏi hạn mức phải hỏi lớp entitlement**, không hỏi
`plans` trực tiếp. Một hàm `entitlements.of(tenant_id)` là ranh giới đó; để router
tự cộng add-on là cách chắc chắn để hai màn hình cho hai con số.

---

## 6. Visibility / Share / Fork là chức năng lõi

Không dùng làm paywall. Có ở cả Free.

Ba khái niệm phải **tách rời**, không suy ra từ nhau:

```
visibility    ∈ { public, tenant, private }
share_policy
fork_policy   ∈ { enabled, tenant_only, disabled }
```

`visibility = public` + `fork_policy = disabled` là hợp lệ. `visibility = private`
+ `fork_policy = tenant_only` cũng hợp lệ.

Fork luôn giữ provenance, và không bao giờ được dùng để làm lộ tài nguyên private.

> **Trạng thái hôm nay:** không có gì trong ba khái niệm này tồn tại trong mã —
> không cột `visibility`, không fork, không share policy. Chúng thuộc mặt phẳng
> registry (`docs/`, xem ghi chú registry ba mặt phẳng) và **chưa được dựng**.
> Với billing điều này nghĩa là: không có gì để gate, và cũng **không được in lên
> bảng giá như tính năng đang có**.

---

## 7. Audit: giữ đủ, khác nhau ở retention

| Gói | Retention |
|---|---|
| Free | 7 ngày |
| Plus | 30 ngày |
| Pro | 180 ngày |
| Enterprise | custom |

"Free → không audit" là hiểu sai. Free **vẫn ghi đầy đủ** mọi hành động quan
trọng; chỉ khả năng truy xuất bị giới hạn 7 ngày.

> **Trạng thái hôm nay:** `audit_log` không có bất kỳ cơ chế retention/purge nào.
> Retention theo gói là **tính năng mới**, không phải cấu hình một thứ đã có.

**Ràng buộc bắt buộc khi dựng:** lượt purge theo retention **không được** chạm vào
các loại sự kiện là bằng chứng pháp lý hoặc bằng chứng đồng thuận (chấp nhận điều
khoản, ký/rút đồng thuận của người ký, sự kiện bảo mật tài khoản). Những thứ đó
được giữ theo nghĩa vụ lưu trữ, không theo gói dịch vụ. Xoá chúng ở ngày thứ 8 vì
một tenant dùng Free là xoá đúng thứ không được phép xoá.

---

## 8. External API và Webhook là quota tích hợp

Hai thứ này **không liên quan** tới frontend của CTU-SignBridge. Free không có
External API vẫn dùng giao diện chính bình thường.

* **External API** — phần mềm bên ngoài gọi vào bằng API key.
* **Webhook** — hệ thống chủ động báo sự kiện ra ngoài (`training.completed`,
  `dataset.version.published`, `export.completed`).

`api_keys` và `webhook_endpoints` giữ nguyên, đổi vai trò thành quota tích hợp của
gói trả phí: Free 0/0, Plus giới hạn, Pro đầy đủ, Enterprise custom.

---

## 9. Subscription tách khỏi tenant

```
TENANT
   └── BILLING_CUSTOMER
          └── SUBSCRIPTION
                 └── PLAN
```

Bảng lõi cần thêm: `billing_customers`, `subscriptions`, `invoices`,
`invoice_items`, `payments`, `billing_webhook_events`, `training_credit_ledger`.
Thêm khi cần: `payment_methods`, `quota_addons` / `entitlement_adjustments`.

### Bốn khái niệm không được lẫn

```
Subscription → quyền dùng gói
Invoice      → khoản phải trả
Payment      → giao dịch tiền thật
Receipt      → xác nhận đã trả
```

Invoice phải **snapshot** thông tin xuất hoá đơn tại thời điểm phát hành:
`legal_name`, `billing_address`, `tax_id`, `billing_email`. Sửa hồ sơ hôm nay
không được làm đổi hoá đơn năm ngoái.

---

## 10. Auto-renew phải đổi nghĩa khi có thanh toán thật

Hôm nay `auto_renew = TRUE` chỉ mở kỳ mới. Khi có cổng thanh toán, luồng là:

```
kỳ sắp hết
    ↓ tạo invoice
    ↓ thử thu tiền
payment succeeded?
    ├─ CÓ    → gia hạn quyền dùng
    └─ KHÔNG → past_due → ân hạn
```

**Chỉ webhook đã xác minh từ nhà cung cấp thanh toán mới được kích hoạt/gia hạn
gói trả phí.** Không bao giờ dựa vào frontend gọi `/payment-success`.

## 11. Hết ân hạn thì hạ về Free, không suspend

Vì đã có Free tier vĩnh viễn, thất bại thanh toán không cần dẫn tới `suspended`:

```
pro / plus → past_due → ân hạn → free
```

Không xoá dữ liệu. Tenant đang dùng 120 GB mà rơi về Free (5 GB):

```
read / export / delete   ✓
upload mới               ✗
```

cho tới khi giảm usage xuống dưới quota Free, hoặc trả tiền/nâng gói lại.

Điều này **đổi hành vi hiện tại** của `subscription_lifecycle.sweep()`, đang chuyển
sang `suspended` ở [subscription_lifecycle.py:356-359](../../backend/app/subscription_lifecycle.py#L356-L359).
`suspended` vẫn tồn tại nhưng chỉ dành cho quyết định của người vận hành.

---

## 12. Mã lỗi phải nói được nguyên nhân

Hôm nay mọi trường hợp trả 402 kèm một câu tiếng Việt. Frontend không phân biệt
được, nên không hiện đúng nút.

Cần một mã máy đọc được, ngoài câu cho người đọc:

```
storage_full
training_credit_exhausted
workspace_limit_reached
project_limit_reached
api_key_limit_reached
webhook_limit_reached
```

Ngưỡng cảnh báo: 80% warning, 90% strong warning, 100% chặn **đúng thao tác đó** —
không chặn cả tenant.

---

## 13. Giao diện

**BillingPage** (người dùng): gói hiện tại · usage · storage · training credits ·
thông tin xuất hoá đơn · phương thức thanh toán · invoices · receipts ·
nâng gói/quản lý đăng ký · add-ons.

**Admin Billing** (người vận hành): active subscriptions · upcoming renewals ·
past due · grace period · payment failures · downgrades · invoices · payments ·
refunds · training credit usage · storage utilization.

Quyền của admin: cấp storage tạm, cấp training credits, đổi gói, miễn trừ billing,
void/refund theo quy trình. **Tất cả đều ghi audit** — chúng là thao tác có hệ quả
tiền bạc.

---

## 14. Những gì tài liệu này KHÔNG hứa

Giữ nguyên nguyên tắc của `SUBSCRIPTION_LIFECYCLE.md`: không viết "sắp có" cho thứ
cần một pháp nhân.

* Hoá đơn điện tử và VAT chính thức cần pháp nhân và kế toán — bước cuối cùng, sau
  tất cả.
* Cổng thanh toán cần merchant account.

Phần mềm chuẩn bị **chỗ** cho chúng (bảng, luồng, webhook adapter), và chỗ trống đó
phải nhìn ra được là chỗ trống.
