# BILLING V8 REVIEW

*Lượt đọc, 25/08/2026. Không đổi CSDL, không bump phiên bản, không sửa mã.*

Đầu vào: [BILLING_MODEL_V6.md](BILLING_MODEL_V6.md) — coi là **giả thuyết cần
kiểm**, không phải đặc tả mặc nhiên đúng. Nó viết 13/08, trước v6 và v7 thật.

---

## A. Thực trạng triển khai

### Bảng

| có | không có |
|---|---|
| `plans` (25 cột), `tenants` (7 cột billing), `tenant_subscriptions`, `tenant_usage_daily`, `project_allocations` | `billing_customers`, `subscriptions`, `invoices`, `invoice_items`, `payments`, `billing_webhook_events`, `training_credit_ledger`, `quota_addons` |

60 bảng toàn CSDL; **không bảng nào chạm tới tiền**.

### Bốn gói đã tồn tại đúng tên

```
free · plus · pro · enterprise
```

`internal / trial / school / institution` **đã biến mất**. `tenants.billing_exempt`
đã có. Các cột `max_workspaces`, `max_projects`, `included_training_credits`,
`audit_retention_days` **đã có**.

Nghĩa là **bước 1 của kế hoạch (mà tài liệu gọi là "v6") đã áp lên sản xuất rồi** —
nhưng không qua một phiên bản lược đồ nào. Phần thêm cột đi qua `ensure_tables()`,
phần đổi mã gói đi qua các câu `UPDATE plans SET plan_code`.

### Hạn mức: khai báo ≠ cưỡng chế

| chỉ số | cột | có cưỡng chế? |
|---|---|---|
| `samples` | `max_samples` | ✅ 2 nơi gọi |
| `classes` | `max_classes` | ✅ |
| `seats` | `max_seats` | ✅ `tenant_admin` |
| `training_jobs_this_month` | `max_training_jobs_per_month` | ✅ |
| `training_jobs_running` | `max_concurrent_training_jobs` | ✅ |
| `training_jobs_queued` | `max_queued_training_jobs` | ✅ |
| `api_keys` | `max_api_keys` | ⚠️ có trong `USAGE_METRICS`, **0 nơi gọi** |
| `webhook_endpoints` | `max_webhook_endpoints` | ⚠️ như trên |
| **storage** | `max_storage_mb` | ❌ **không phải một chỉ số** |
| workspace | `max_workspaces` | ❌ |
| project | `max_projects` | ❌ |
| training credits | `included_training_credits` | ❌ |
| audit retention | `audit_retention_days` | ❌ |

Năm cột cuối chỉ xuất hiện ở hai chỗ trong `plans.py`: một dict mặc-định-0 và một
dict cờ. **Không nơi nào đọc chúng để quyết định gì.**

### Nguồn sự thật

```
ĐỌC   plans.check_quota:145      SELECT plan_code, billing_status FROM tenants
      workspace_admin._tenant_ceiling  SELECT plan_code FROM tenants

GHI   tenant_admin.change_plan   UPDATE tenants SET plan_code = …
                               + _open_subscription(...)  -> tenant_subscriptions
      (cả hai trong CÙNG một khối `with system_scope`)
```

### Vòng đời

`subscription_lifecycle.sweep()` chạy: nhắc trước hạn → hết kỳ → `past_due` + ân
hạn → **hết ân hạn thì `suspended`**.

### API và giao diện

`GET /billing/plans` · `/billing/me` · `/billing/usage` · `/billing/platform-usage` ·
`PATCH /billing/plans/{code}` + 2 PATCH khác.
`BillingPage.tsx` + `AdminBillingPage.tsx` — **0 lần nhắc invoice/payment/hoá đơn**.

---

## B. Thiết kế tài liệu đề xuất

Bốn gói, hạn mức theo bảng §1; `free` vĩnh viễn (`billing_period='none'`, không
trial); membership **bỏ khỏi quota**; storage là **quota ràng buộc duy nhất của dữ
liệu** và phải chặn **ở đường ghi** bằng bộ đếm bền + đối chiếu hằng ngày; training
chuyển từ thời gian sang **credits có sổ cái**; quota thực tế đọc qua lớp
**entitlement** = gói + mua thêm; audit giữ đủ, khác nhau ở retention; hết ân hạn
**hạ về Free chứ không suspend**; mã lỗi máy đọc được; và một tầng
`billing_customers → subscriptions → invoices → payments` khi có pháp nhân.

Kế hoạch phiên bản của tài liệu: v6 = bước 1, v7 = bước 2–4, v8 = bước 5–7,
v9 = bước 8–9.

---

## C. Khác biệt và mâu thuẫn

### C1. Kế hoạch phiên bản của tài liệu đã hết hiệu lực

v6 và v7 **đã bị dùng cho việc khác** và đã đóng dấu trên sản xuất:

```
v6  gỡ bất biến "buổi thu có một người ký"   checksum afb8fefd…
v7  con trỏ registry NULL thay vì mốc 0      checksum 879e6c57…
```

Nên **phiên bản lược đồ đầu tiên của Billing là v8**, và toàn bộ ánh xạ
bước→phiên bản trong tài liệu phải đánh số lại. Đây không phải chi tiết hình
thức: mục 0 của chính tài liệu nói payload đã áp thì không sửa được.

### C2. Số liệu trong CSDL lệch bảng giá của tài liệu

| | tài liệu | CSDL |
|---|---|---|
| Free storage | 5 GB | **2 GB** |
| Pro storage | 250 GB | **500 GB** |
| Free API key | 0 | **1** |
| Plus webhook | 2 | **3** |
| Training đồng thời | 1 / 2 / 4 | **1 / 1 / 2** |
| Thành viên | ∞ mọi gói | **3 / 25 / 200**, và **đang cưỡng chế** |
| Sample | ∞ | **500 / 20k / 200k**, đang cưỡng chế |
| Class | ∞ | **30 / 500 / 5k**, đang cưỡng chế |

Ba dòng cuối là mâu thuẫn **hành vi**, không phải sai số: tài liệu nói ba quota ấy
không tồn tại, còn hệ thống đang chặn người dùng bằng chúng.

### C3. Ba cột được khai nhưng chết

`max_storage_mb`, `included_training_credits`, `audit_retention_days` (cộng
`max_workspaces`, `max_projects`) nằm trong bảng giá và trả ra API, nhưng không có
đường nào đọc để chặn. **Bảng giá đang hứa những giới hạn mà hệ thống không thi
hành** — và điều đó nguy hiểm theo cả hai chiều: người dùng Free có thể ghi vượt
2 GB không ai chặn, còn người mua Pro thì trả tiền cho một con số không có nghĩa.

### C4. Hết ân hạn: mã và tài liệu ngược nhau

`subscription_lifecycle.py` đặt `suspended`; tài liệu §11 nói phải **hạ về Free**.
Đây là quyết định sản phẩm chưa chốt, không phải lỗi.

### C5. Tài liệu in lên bảng giá thứ chưa tồn tại

§1 có dòng *Visibility / Share / Fork / Provenance ✓* cho cả bốn gói, trong khi
chính §6 thừa nhận **không có gì trong ba khái niệm đó tồn tại trong mã**. Bảng
giá không được liệt kê tính năng chưa dựng.

### C6. Sáu câu hỏi bạn đặt — trả lời dứt điểm

| câu hỏi | trả lời |
|---|---|
| nguồn sự thật của subscription | **`tenants.plan_code`** là nguồn ĐỌC — mọi phép cưỡng chế đọc nó. `tenant_subscriptions` là **lịch sử**. |
| thông tin gói ở tenant là cache hay sự thật | Về ý định là projection; về thực tế nó **là** sự thật, vì không ai đọc `tenant_subscriptions` để cưỡng chế. Và **không ràng buộc nào** giữ hai bên đồng bộ — chỉ nhờ `change_plan` ghi cả hai trong một khối. |
| quota tính/enforce ở đâu | `plans.check_quota` → `guard_quota` tại điểm cuối ghi. Đếm bằng `count(*)` trên bảng nguồn, cố ý không nuôi bộ đếm. |
| đổi gói có lịch sử hay ghi đè | **Cả hai**: ghi đè `tenants.plan_code` + nối một dòng `tenant_subscriptions`. |
| Free/Plus/Pro/Enterprise là mới hay phải migrate | **Đã migrate xong.** Không còn `internal/trial/school/institution`. |
| v8 có gồm thu tiền không | **Không.** Không bảng, không cổng, không invoice/payment ở UI. v8 chỉ nên là **quản lý gói / đăng ký / quyền dùng**. |

---

## D. Mô hình canonical đề xuất cho v8

1. **`tenants.plan_code` là nguồn ĐỌC chính thức**, được thừa nhận thay vì mặc
   nhiên. `tenant_subscriptions` là sổ lịch sử, chỉ nối thêm.
2. **Một hạn mức chỉ tồn tại nếu có nơi cưỡng chế nó.** Cột nào không cưỡng chế
   thì hoặc dựng đường cưỡng chế, hoặc bỏ khỏi bảng giá. Không giữ trạng thái thứ
   ba.
3. **Storage là quota ràng buộc của dữ liệu** (theo tài liệu §3), thay cho
   `samples`/`classes`.
4. **Membership không phải quota** (§2) — bỏ `seats`.
5. **Training: giữ giới hạn đồng thời, bỏ giới hạn số lượt/tháng.** Credits có sổ
   cái là bước sau.
6. **Không tiền trong v8.**

---

## E. Thay đổi CSDL cần thiết

Chỉ những câu **một chiều** mới cần v8; phần thêm đi qua `ensure_tables()`.

| # | câu | loại |
|---|---|---|
| E1 | `ALTER TABLE plans DROP COLUMN max_seats` | một chiều |
| E2 | `DROP COLUMN max_samples`, `DROP COLUMN max_classes` | một chiều |
| E3 | `DROP COLUMN max_training_jobs_per_month` | một chiều |
| E4 | `CREATE TABLE tenant_storage(tenant_id PK, bytes_used BIGINT NOT NULL DEFAULT 0, checked_at)` | thêm |
| E5 | `UPDATE plans SET …` chỉnh số cho khớp bảng giá đã chốt | một chiều |

E1–E3 chỉ nên chạy **sau khi** gỡ hết nơi đọc (xem F). Đảo thứ tự là tự tạo ra sự
cố `column does not exist` trên đường ghi nóng.

---

## F. Thay đổi ứng dụng / API

| # | việc | ghi chú |
|---|---|---|
| F1 | Gỡ `seats`, `samples`, `classes`, `training_jobs_this_month` khỏi `USAGE_METRICS` và mọi nơi gọi `guard_quota` | 5 nơi gọi |
| F2 | Thêm chỉ số `storage` với bộ đếm bền + pre-check ở đường ghi | phần lớn công sức của v8 |
| F3 | Lượt đối chiếu hằng ngày: đi bộ cây thư mục, ghi đè bộ đếm nếu lệch, log WARNING | celery-beat |
| F4 | Nối `api_keys` và `webhook_endpoints` vào đường cưỡng chế | 2 điểm cuối |
| F5 | Nối `max_workspaces` / `max_projects` vào đường tạo | 2 điểm cuối |
| F6 | Mã lỗi máy đọc được (§12) thay cho 402 + một câu tiếng Việt | API + UI |
| F7 | `BillingPage` bỏ "Thời gian huấn luyện", thêm storage thật | UI |

---

## G. Chiến lược migration / backfill

1. Gieo `tenant_storage.bytes_used` bằng một lượt đi bộ **trước** khi bật pre-check
   — bật cổng trên một bộ đếm 0 sẽ chặn mọi người ngay lập tức, còn bật trên một bộ
   đếm chưa gieo mà mặc định "không giới hạn" thì cổng vô nghĩa. Hậu điều kiện:
   mọi tenant đang hoạt động có một dòng, và tổng khớp lượt đi bộ trong sai số.
2. Chốt bảng giá **trước** E5. Con số hiện tại trong CSDL là thứ người dùng đang
   sống với; đổi chúng là đổi hợp đồng.
3. E1–E3 đi **sau** F1 ít nhất một lượt triển khai.

---

## H. Tiêu chí nghiệm thu

* Không cột nào trong `plans` được trả ra API mà không có đường cưỡng chế — hoặc
  cưỡng chế, hoặc không có trong bảng.
* Tenant Free ghi vượt trần dung lượng bị chặn **ở lượt ghi**, không phải hôm sau.
* Bộ đếm dung lượng lệch lượt đi bộ thì có log WARNING và tự sửa.
* Xoá tệp làm bộ đếm **giảm**.
* Đọc / tải về / xoá **vẫn chạy** khi đã đầy (§3).
* Mã lỗi phân biệt được `storage_full` với `project_limit_reached`.
* `tenants.plan_code` và dòng `tenant_subscriptions` đang mở luôn cùng một gói —
  có test ghim.
* Không mã nào nhắc lại con số hạn mức (§1: "không hằng số nào trong mã").

---

## I. Hoãn lại

| việc | vì sao hoãn |
|---|---|
| `billing_customers`, `invoices`, `payments`, webhook thanh toán | cần pháp nhân + merchant account (§14 của chính tài liệu) |
| Training credit ledger | đáng làm, nhưng độc lập với việc bịt lỗ hạn mức; nên là v9 |
| Entitlement add-on (mua thêm) | không có người mua thì không có gì để cộng |
| Audit retention theo gói | tính năng mới, và có ràng buộc pháp lý (§7) — không được xoá bằng chứng đồng thuận |
| Visibility / Share / Fork | chưa tồn tại; phải gỡ khỏi bảng giá của tài liệu |
| Hạ về Free thay vì suspend | quyết định sản phẩm; nhỏ về mã, lớn về hệ quả |

---

## Đề xuất phạm vi v8 tối thiểu đóng được

**Phải có:** F1 + F2 + F3 + E4 + G1 — *bịt khoảng cách giữa hạn mức được khai và
hạn mức được thi hành, với storage là quota dữ liệu duy nhất.*

**Nên có nếu còn sức:** F4, F5, F6.

**Không làm trong v8:** toàn bộ mục I.

Lý do chọn ranh giới này: trạng thái tệ nhất hiện nay không phải "thiếu tính năng"
mà là **bảng giá nói một đằng, hệ thống làm một nẻo**. Một tenant Free hôm nay bị
chặn ở 500 mẫu — con số tài liệu bảo phải bỏ — và ghi được bao nhiêu GB tuỳ thích —
con số tài liệu bảo phải là ràng buộc chính. v8 đóng đúng khoảng cách đó, và không
cần một đồng nào chảy qua hệ thống để đóng được.
