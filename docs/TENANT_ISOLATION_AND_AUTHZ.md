# Phân quyền và cách ly tenant trong CTU.SignBridge — hệ thống hiện tại

*Đo trên bản đang chạy ngày 15/08/2026. Mọi con số đều kèm cách tái lập; không
con số nào chép từ tài liệu thiết kế.*

> **Tài liệu này định nghĩa tiêu chí TRƯỚC, đo SAU, kết luận CUỐI.** Nó không
> tuyên bố hệ thống đã đạt mức cách ly nào. Kết luận đó thuộc về chương kết quả,
> và chỉ được viết khi scorecard ở §7 xanh hết.

---

## 1. Ba trục đánh giá

Casbin và RLS trả lời hai câu hỏi khác nhau, nên phải đo bằng hai bộ chỉ số khác
nhau, rồi mới đo phần giao nhau:

| Trục | Câu hỏi | Cơ chế | Đơn vị |
|---|---|---|---|
| **A. Authorization correctness** | Người này được phép làm hành động này không? | Casbin RBAC theo domain | hành động (`sample.delete`) |
| **B. Tenant data isolation** | Truy vấn này được chạm những hàng nào? | PostgreSQL RLS + ranh giới đặc quyền | hàng (`tenant_id`) |
| **C. End-to-end** | Có thao tác trái quyền hoặc xuyên tenant nào thành công không? | bộ kiểm đối kháng qua API | request |

Hai lớp **không thay thế nhau**:

```
có quyền sample.delete, nhắm vào mẫu của tenant khác   → Casbin cho qua, B phải chặn
đúng tenant mình, nhưng vai không có quyền delete      → RLS cho qua, A phải chặn
```

Và kiểu lỗi mỗi lớp bắt được cũng khác nhau:

```
lập trình viên quên `WHERE tenant_id = %s`        → A không bắt, B bắt
người dùng gọi endpoint ngoài vai của mình        → B không bắt, A bắt
```

---

## 2. Trục A — Casbin

### 2.1 Mô hình

`backend/app/authorization/model.conf` — RBAC có domain:

```
r = sub, dom, perm         sub  = "user:<uuid>"
p = role, perm             dom  = "sys" | "ten:<id>" | "ws:<uuid>" | "prj:<uuid>"
g = _, _, _                perm = "sample.annotate"

m = g(r.sub, p.role, r.dom) && r.perm == p.perm
```

Ba quyết định thiết kế đáng nêu:

1. **`p` không mang domain.** Quan hệ role→quyền độc lập với nơi chốn: "Tenant
   Administrator gồm những quyền này" đúng ở mọi tenant. Chính `g` mới gắn người
   vào role *tại* một domain. Nhét domain vào `p` sẽ nhân bản `role_permissions`
   theo số tenant, biến mỗi tenant mới thành một lần sao chép policy.
2. **So khớp CHÍNH XÁC**, không `keyMatch`/regex. Khớp mẫu sẽ khiến `sample.read`
   khớp luôn `sample.readonly` và mọi mã quyền tương lai cùng tiền tố — một lỗ tự
   mở rộng theo thời gian mà không ai phải sửa mã.
3. **Thuần allow-list**, không policy phủ định (`e = some(where (p.eft == allow))`).
   DENY tường minh sẽ tạo thứ tự ưu tiên giữa allow và deny, phá nguyên tắc thống
   trị phạm vi mà cây bốn tầng dựa vào, và làm câu "vì sao người này bị từ chối"
   không còn trả lời được bằng cách nhìn một chỗ.

### 2.2 Cây phạm vi và 13 vai dựng sẵn

```
SYSTEM ─── TENANT ─── WORKSPACE ─── PROJECT
```

| Tầng | Vai |
|---|---|
| SYSTEM (2) | `platform_administrator`, `platform_auditor` |
| TENANT (5) | `tenant_owner`, `tenant_administrator`, `tenant_editor`, `community_member`, `community_curator` |
| WORKSPACE (2) | `workspace_administrator`, `workspace_viewer` |
| PROJECT (4) | `project_administrator`, `project_contributor`, `project_reviewer`, `project_viewer` |

Không có `tenant_viewer`: quyền chỉ-đọc ở tầng tenant là `community_member`, và
thêm một vai gần trùng chỉ tạo hai đường làm cùng một việc.

### 2.3 Trình tự quyết định

`authorization_service.py` là một cửa duy nhất, thứ tự bắt buộc:

```
1. Xác thực                                (xong trước khi vào)
2. Tư cách thành viên còn hiệu lực?        ← đọc NGUỒN THẬT, không đọc cache
3. Casbin: có quyền không?                 ← DENY thì DỪNG
4. Quyền này có đòi mã hành động không?    ← chỉ chạy khi ĐÃ ALLOW
5. Thực hiện + audit + outbox
```

Bước 4 **không bao giờ** biến DENY thành ALLOW. Mã hành động là bằng chứng "đúng
người đang ngồi đây", không phải một quyền. Đảo hai bước tạo ra hệ thống mà nhập
đúng mã thì làm được mọi thứ.

Bước 2 đọc nguồn thật vì giữa lúc thu hồi quyền và lúc mọi tiến trình nạp lại
policy có một khoảng trễ. Với thao tác thường, khoảng đó chấp nhận được; với
`tenant.purge` hay `role.manage` thì không.

### 2.4 Casbin hiện KHÔNG phải là bên cưỡng chế

```
AUTHZ_MODE=shadow
```

Ba chế độ: `legacy` → `shadow` → `casbin`. Ở `shadow`, **hệ cũ quyết định** —
`users.is_admin` cộng `tenant_members.role`. Casbin chạy song song trên mọi
request và mọi bất đồng được ghi lại, nhưng **không request nào bị đổi kết quả**.

Phát biểu đúng ở thời điểm đo:

> Casbin đã được tích hợp và đang chạy đối chiếu trên mọi quyết định phân quyền;
> nó **chưa** phải là bên cưỡng chế.

Đây là cùng một khoảng cách "tồn tại ≠ cưỡng chế" mà §4 nêu cho RLS, chỉ khác mặt
phẳng. Luận văn không được viết "phân quyền do Casbin cưỡng chế" chừng nào
`AUTHZ_MODE` chưa là `casbin`.

Hệ cũ **được suy ra chứ không chép lại**: `_legacy_decision` đọc chính các vai
dựng sẵn (`tenant_editor` được định nghĩa là tập quyền tương đương
`tenant_members.role = 'editor'`). Nhờ vậy mọi mismatch còn lại nhất định là khác
biệt **dữ liệu** — assignment chưa backfill, membership lệch, vai bị vô hiệu —
chứ không phải nhiễu do hai bảng ánh xạ trôi khỏi nhau.

### 2.5 Chỉ số của giai đoạn chuyển giao

$$\text{ADAR} = \frac{N_{\text{quyết định hệ cũ} \;=\; \text{quyết định Casbin}}}{N_{\text{quyết định được so sánh}}}$$

Trước khi cutover: **ADAR = 100%**, hoặc mọi mismatch còn lại phải được phân loại
và giải trình, không còn mismatch chưa xử lý.

Chỉ số này cho luận văn bằng chứng về *quá trình* chuyển đổi chứ không chỉ kết
quả:

```
legacy → shadow comparison → mismatch = 0 → Casbin enforcement
```

khác hẳn với "cài Casbin rồi bật".

---

## 3. Trục B — RLS

### 3.1 Vị từ

```sql
USING      ( current_setting('app.system_scope', true) = 'on'
             OR tenant_id = current_setting('app.tenant_id', true) )
WITH CHECK ( … cùng biểu thức … )
```

`USING` và `WITH CHECK` cố ý **giống hệt nhau**: `USING` quyết định hàng nào hiện
ra với SELECT/UPDATE/DELETE, `WITH CHECK` quyết định hàng nào được phép sinh ra
bởi INSERT/UPDATE. `USING` hẹp hơn `WITH CHECK` sẽ cho phép ghi ra hàng mà chính
mình không đọc lại được.

Mọi bảng chịu RLS đều bật `FORCE ROW LEVEL SECURITY`, nên **chủ sở hữu bảng cũng
chịu policy**.

### 3.2 Hai điểm tinh tế

* `tenant_members` **không** bật RLS vì PDM v5 đã biến nó thành VIEW trên
  `memberships`. Policy sống ở bảng nền; view khai `security_invoker = true` nên
  truy vấn qua nó chạy dưới quyền **người gọi**. Thứ phải canh là thuộc tính đó:
  bỏ nó thì view chạy bằng quyền chủ sở hữu và mọi tenant đọc được thành viên của
  mọi tenant khác.
* `user_totp` và `user_recovery_codes` **cố ý** không chịu RLS. Chúng thuộc mặt
  phẳng danh tính và được đọc *giữa chừng lúc đăng nhập*, trước khi hệ thống biết
  người này thuộc tenant nào.

  Cần gọi đúng tên hiện tượng ở đây: RLS trả 0 hàng là RLS đang **thu hẹp** dữ
  liệu đúng chức năng của nó. Cái fail-open nằm ở **ngữ nghĩa ứng dụng** — logic
  đăng nhập diễn giải "0 hàng" thành "người này không bật 2FA", và chính phép
  diễn giải đó vô hiệu hoá lớp bảo vệ thứ hai. Đây là *application-semantic
  fail-open*, không phải RLS fail-open. Dạng lỗi này đã xảy ra ba lần trong hai
  ngày ở mặt phẳng danh tính.

### 3.3 Fail-closed khi thiếu ngữ cảnh

Không đặt `app.tenant_id` thì vị từ cho ra NULL chứ không phải TRUE, nên truy vấn
thấy **0 hàng**. Thiếu ngữ cảnh không rơi về phạm vi toàn cục mà bị từ chối. Đây
là claim hợp lệ, và nó đã có giá trị thực tế: chính cơ chế này bắt được ba sự cố
fail-open nói trên.

---

## 4. Ranh giới tin cậy

### 4.1 Ngữ cảnh tenant do chính vai ứng dụng tự khai

Dưới `voya_test_app`, **không** dùng `system_scope`:

```sql
SELECT set_config('app.tenant_id', 'default', false);
SELECT count(*) FROM classes;         -- 63
UPDATE classes SET region = region;   -- UPDATE 63
```

Sentinel `app.system_scope` không phải cánh cửa thứ nhất — nó là cánh cửa thứ
hai. Cửa thứ nhất là danh tính tenant, và cửa đó do chính vai bị ràng buộc tuyên
bố. Hệ quả:

* Vá `pg_has_role` cho `system_scope` **không** đóng được cách ly tenant: vai ứng
  dụng chỉ cần bỏ qua sentinel và đặt thẳng `app.tenant_id`.
* Bật RLS cho `tenants` với chính sách "chỉ thấy dòng của mình" cũng không cưỡng
  chế được gì trước một vai tự chọn được "mình" là ai.

### 4.2 Điều tương đương ở mặt phẳng phân quyền

Casbin adapter dựng `p` và `g` từ **sáu** bảng, và `voya_app` giữ đủ bốn quyền
DML trên cả sáu:

| Bảng | Vai trò | RLS | GRANT của `voya_app` |
|---|---|---|---|
| `permissions` | dựng `p` | **không** | `SELECT, INSERT, UPDATE, DELETE` |
| `role_permissions` | dựng `p` | **không** | `SELECT, INSERT, UPDATE, DELETE` |
| `roles` | dựng `p` | có | `SELECT, INSERT, UPDATE, DELETE` |
| `role_assignments` | dựng `g` | **không** | `SELECT, INSERT, UPDATE, DELETE` |
| `memberships` | phạm vi của `g` | có | `SELECT, INSERT, UPDATE, DELETE` |
| `users` | `g` tầng hệ thống | có | `SELECT, INSERT, UPDATE, DELETE` |

Không đường chạy nào cần những quyền ghi đó: `permissions`, `role_permissions` và
`roles` chỉ được `authorization/seed.py` viết, mà seed chạy trong `_apply_schema()`
dưới `_migration_cursor()` — tức DSN của `admin`. `role_assignments` chỉ được
`cli/backfill_authz.py` viết. Không router nào tạo vai hay gán quyền lúc chạy.

Ba bảng không có RLS là chỗ nặng nhất, và `role_assignments` nặng nhất trong ba:
nó **không mang `tenant_id`** (phạm vi đọc từ `memberships`), không có policy, và
ghi được tự do — tức là một câu `INSERT` đủ để tự gán `platform_administrator`.

Nghĩa là **vai bị Casbin quản lý cũng chính là vai sửa được policy quản lý nó**.
Hôm nay điều đó vô hại vì Casbin đang ở `shadow` và không quyết định gì. Kể từ
lúc `AUTHZ_MODE=casbin`, nó trở thành một nguyên thuỷ leo thang đặc quyền có cùng
hình dạng với việc tự khai `app.tenant_id`: **thẩm quyền do chính bên bị ràng
buộc tự tuyên bố.**

### 4.3 Hai mức cách ly

**Mức I — cách ly do CSDL cưỡng chế, dưới ngữ cảnh tenant đã xác thực.**

Kẻ tấn công là người dùng API: gọi API với ID của tenant khác, đoán resource ID,
sửa tham số, gọi sai endpoint, lợi dụng truy vấn quên lọc tenant. Kẻ đó **không**
có credential CSDL và **không** thực thi được SQL tuỳ ý.

```
backend xác thực U thuộc tenant A
      ↓ thiết lập ngữ cảnh A
      ↓ truy vấn quên WHERE tenant_id
RLS vẫn chỉ cho thấy A
```

Đây là **mức cách ly mà hệ thống hướng tới và là phạm vi đánh giá của luận văn**.
Việc xác nhận đạt Mức I do scorecard §7 và bộ kiểm đối kháng §6 quyết định — chưa
được tuyên bố ở đây.

**Mức II — cách ly chống cả vai CSDL hướng-tenant bị chiếm.**

```
kẻ tấn công thực thi SQL dưới voya_app
      ↓ vẫn không tự nhận được là tenant B
```

Hệ thống **không đạt** mức này, và phép đo §4.1 là bằng chứng trực tiếp.

### 4.4 Phát biểu đúng

Không viết:

> ~~Cách ly tenant được cưỡng chế tại tầng CSDL và không phụ thuộc tính đúng đắn
> của tầng ứng dụng.~~
>
> ~~Even a compromised application database role cannot access another tenant.~~
>
> ~~Bảo đảm cách ly không tự thu hồi được.~~

Viết:

> Ngữ cảnh tenant được xác lập từ danh tính và tư cách thành viên đã xác thực ở
> tầng ứng dụng; sau đó PostgreSQL RLS cưỡng chế phạm vi hàng một cách độc lập
> tại tầng CSDL, nhờ đó truy vấn thiếu bộ lọc tenant hoặc truy cập tài nguyên của
> tenant khác bị từ chối mặc định, và hệ thống hỏng-thì-đóng khi thiếu ngữ cảnh.

Về việc tách hai DSN, chỉ phát biểu đúng phần chứng minh được:

> Vai chạy ứng dụng không có SUPERUSER, BYPASSRLS hay quyền DDL, nên **không thể
> trực tiếp vô hiệu hoá RLS hoặc sửa policy/lược đồ bằng các đặc quyền đó**.

Không mở rộng thành "không tự thu hồi được": vai ấy tuy không tắt được RLS nhưng
**đổi được chính đầu vào mà policy tin cậy** (§4.1), và sửa được bảng policy của
Casbin (§4.2).

Nếu hội đồng hỏi *"user tự đổi tenant_id thì sao?"* — câu trả lời không phải là
thiết kế mà là số đo TCBVR ở §6.4.

---

## 5. Số đo hiện tại

| Chỉ số | Giá trị | Nguồn |
|---|---|---|
| Bảng `public` | 58 | `pg_class relkind='r'` |
| Bảng bật RLS | 32 | `relrowsecurity` |
| Bảng bật FORCE RLS | 32 / 32 = **100%** | `relforcerowsecurity` |
| Policy | 32 | `pg_policies` |
| Bảng mang `tenant_id` | 34 | `information_schema.columns` |
| Bảng tenant có RLS | 32/34 = **94,1%** | thiếu: `tenants`, `tenant_purges` |
| `voya_app` SUPERUSER / BYPASSRLS | `false` / `false` | `pg_roles` |
| `voya_app` CREATEDB / CREATEROLE | `false` / `false` | `pg_roles` |
| Vai lúc chạy | `voya_app` | `DATABASE_URL` |
| Vai chạy DDL | `admin` (DSN riêng) | `MIGRATION_DATABASE_URL` |
| `DB_STRICT_ISOLATION` | `1` | `.env` |
| `AUTHZ_MODE` | `shadow` | `.env` |
| `voya_app` trên `tenants` | `SELECT, INSERT, UPDATE, DELETE` | `role_table_grants` |
| `voya_app` trên `tenant_purges` | `SELECT, INSERT, UPDATE, DELETE` | `role_table_grants` |
| `voya_app` trên 6 nguồn phân quyền hữu hiệu | `SELECT, INSERT, UPDATE, DELETE` | `role_table_grants` (xem §4.2) |
| Trong đó không có RLS | `permissions`, `role_permissions`, `role_assignments` | `relrowsecurity` |

Hai dòng đầu về vai phải đọc cùng nhau: RLS **thật sự có hiệu lực lúc chạy** vì
`DATABASE_URL` trỏ vào một vai không superuser, không BYPASSRLS. Nếu ứng dụng nối
bằng `admin` thì 32 policy kia là trang trí.

### Hai bảng chưa được bảo vệ — cả hai đều là khoảng trống thật

Ban đầu có lập luận rằng `tenant_purges` là bảng control-plane nên không cần RLS:
sau khi xoá thì không còn tenant nào để phạm vi hoá theo. Lập luận đó chỉ đứng
vững nếu vai ứng dụng **không có đường truy cập trực tiếp**. Phép đo bác bỏ điều
đó: `voya_app` có đủ bốn quyền DML trên `tenant_purges`, y hệt trên `tenants`.

Nên ở trạng thái hiện tại, **cả hai đều là khoảng trống cách ly thật**, không
phải ngoại lệ có giải trình.

> **Cập nhật 16/08/2026 — bảng số ở §5 là ẢNH CHỤP CỦA CƠ SỞ DỮ LIỆU ĐÃ TRIỂN
> KHAI, đo TRƯỚC bản vá.** Trong mã nguồn, `tenants` đã được đưa vào `RLS_TABLES`
> và ba đường đọc xuyên tenant hợp lệ đã được bọc phạm vi tường minh. Nhưng con
> số `32/34` chỉ đổi sau khi migration chạy trên chính cơ sở dữ liệu ấy và được
> **đo lại**, nên nó được giữ nguyên ở đây thay vì sửa theo mã. `tenant_purges`
> chưa được xử lý ở cả hai phía. Đừng chép `94,1%` sang quyển luận văn như số
> cuối: hoặc đo lại sau migration, hoặc ghi kèm ngày đo và trạng thái mã.

---

## 6. Bộ tiêu chí

Đo **kết quả bảo mật**, không đo cấu hình. "Đã bật RLS" là một dòng cấu hình; "0
hàng rò qua 500 thao tác đối kháng" là một kết quả.

### 6.1 Coverage: bảo vệ, không phải RLS

Đích không phải 34/34 bảng đều dùng RLS. Một bảng control-plane được cách ly tốt
mà không cần RLS, miễn là chứng minh được.

$$\text{Isolation Protection Coverage} = \frac{N_{\text{bảng tenant có cơ chế cách ly ĐƯỢC KIỂM CHỨNG}}}{N_{\text{bảng tenant}}} = 100\%$$

Một bảng được tính là **protected** nếu thuộc một trong hai loại:

```
A.  RLS + FORCE + policy, có test
B.  vai ứng dụng thường KHÔNG có quyền truy cập trực tiếp,
    và chỉ tới được qua một đường điều khiển hẹp (capability/route riêng)
```

Cách này không ép `tenant_purges` phải dùng RLS chỉ để làm đẹp số. Nhưng theo
phép đo §5, hôm nay nó **chưa đạt loại nào** — cũng như `tenants`.

### 6.2 Ba nhóm tấn công, ba chỉ số — tên phải khớp thứ nó đo

Bộ 500 thao tác chia theo trục bị tấn công, và **mỗi nhóm được đếm bởi chỉ số
mang đúng tên của nó**. Nhóm A không có yếu tố xuyên tenant nào, nên gộp nó vào
một chỉ số tên "Cross-Tenant …" sẽ làm chính cái tên nói sai:

$$\text{CTIVR} = \frac{N_{\text{thao tác xuyên tenant thành công}}}{N_{\text{lần thử xuyên tenant (B + C)}}} = 0$$

$$\text{UASR} = \frac{N_{\text{hành động ngoài quyền thành công}}}{N_{\text{lần thử sai quyền (A)}}} = 0$$

$$\text{SVSR} = \frac{N_{\text{vi phạm bảo mật thành công}}}{N_{\text{toàn bộ lần thử (A + B + C)}}} = 0$$

`SVSR` là con số tổng hợp duy nhất được phép gộp cả ba nhóm. Hội đồng nhìn tên
chỉ số phải biết ngay nó đo cái gì.

| Nhóm | Nội dung | Lớp phải bắt |
|---|---|---|
| **A. Authorization** | đúng tenant, sai quyền | Casbin |
| **B. Isolation** | đúng quyền, sai tenant | RLS / ranh giới đặc quyền |
| **C. Combined** | sai quyền **và** sai tenant | không lớp nào được fail-open |

Ví dụ cụ thể cho từng nhóm:

```
A   tenant_editor@A  DELETE sample@A   nhưng vai không có sample.delete
B   tenant_admin@A   DELETE sample@B
C   project_viewer@A UPDATE sample@B
```

Phân bố đề xuất cho nhóm B và C (kế thừa ma trận cũ):

```
SELECT tài nguyên tenant khác        120
UPDATE tài nguyên tenant khác        100
DELETE tài nguyên tenant khác         80
INSERT với tenant_id của tenant khác  80
membership/tài nguyên tenant khác     80
không có ngữ cảnh tenant              40
```

### 6.3 UASR — hai ca bắt buộc

Hai ca dưới đây kiểm đúng hợp đồng §2.3 và phải nằm trong nhóm A:

```
U có tenant_editor tại A  →  KHÔNG tự có tenant_editor tại B      (cross-domain)
Casbin DENY + nhập đúng mã hành động  →  VẪN DENY                  (bước 4)
```

### 6.4 UPMSR — không ai tự sửa được thẩm quyền của chính mình

$$\text{Unauthorized Policy Mutation Success Rate} = \frac{N_{\text{lần sửa trạng thái phân quyền hữu hiệu trái phép thành công}}}{N_{\text{lần thử}}} = 0$$

Đo GRANT trên mấy bảng mang chữ "policy" trong tên là **chưa đủ**. Điều phải bảo đảm rộng hơn:

> Không tồn tại đường chạy nào cho phép ứng dụng hướng-tenant tự sửa **trạng thái
> phân quyền hữu hiệu** ngoài nghiệp vụ đã được authorize.

"Trạng thái phân quyền hữu hiệu" là mọi thứ mà Casbin adapter đọc để dựng `p` và
`g`, không chỉ các bảng mang chữ "policy" trong tên. Theo `adapter.py`, đó là
**sáu** bảng: `permissions`, `role_permissions`, `roles` (dựng `p`) và
`role_assignments` ⋈ `memberships` ⋈ `users` (dựng `g`).

Kịch bản phải chặn được:

```
voya_app không UPDATE role_assignments được         ✓
nhưng UPDATE được memberships → Casbin nạp lại
      → người dùng tự thành administrator           ✗  vẫn là leo thang
```

Điều này **không** có nghĩa cấm mọi cập nhật membership — quản trị viên tenant
hợp lệ vẫn phải quản lý thành viên. Ý là mọi mutation lên trạng thái phân quyền
hữu hiệu phải đi qua một nghiệp vụ đã authorize, không có đường ghi thô nào ngoài
luồng.

Ca kiểm:

```
người dùng thường  →  sửa role / assignment / membership hữu hiệu   → DENY
tenant admin tại A →  đổi vai ở tenant B                            → DENY
gán vai nhạy cảm ở tầng nền tảng, thiếu quyền hoặc thiếu mã hành động → DENY
```

### 6.5 TCBVR — chứng minh câu "client không đổi được tenant"

$$\text{TCBVR} = \frac{N_{\text{request thành công với ngữ cảnh tenant không thuộc người gọi}}}{N_{\text{lần thử giả mạo ngữ cảnh}}} = 0$$

```
U thuộc tenant A

request tenant=A            → bình thường
request sửa tenant_id=B     → DENY / 404
resource_id thật của B      → DENY / 404
workspace/project của B     → DENY / 404
API key của B               → không dùng được như của A
```

### 6.6 Khả năng phân biệt đối tượng

```
GET /resource/<id-thật-của-B>   →  404
GET /resource/<id-ngẫu-nhiên>   →  404
```

Hai kết quả phải **quan sát tương đương**. Trả 403 cho cái đầu và 404 cho cái sau
biến API thành máy trả lời "tài nguyên này có tồn tại không" cho tenant khác.

### 6.7 SMDR — sức mạnh của bộ test

$$\text{SMDR} = \frac{N_{\text{đột biến bị phát hiện}}}{N_{\text{đột biến tiêm vào}}} = 100\%$$

Cố ý phá từng bất biến và **yêu cầu test phải đỏ**: bỏ policy, bỏ FORCE, bỏ tenant
scope, bỏ `WITH CHECK`, cho `tenant_id` của tenant khác, bỏ `security_invoker` của
view `tenant_members`, hạ `AUTHZ_MODE`, gỡ một quyền khỏi vai dựng sẵn.

Đây là bằng chứng mạnh hơn hẳn code coverage: nó chứng minh bộ test *phát hiện
được* mất mát bảo mật, chứ không chỉ chạy qua dòng mã.

---

## 7. Scorecard

### A. Phân quyền — Casbin

| Chỉ số | Đích | Hiện tại |
|---|---|---|
| `AUTHZ_MODE` | `casbin` | **`shadow`** |
| Shadow mismatch chưa giải quyết | 0 | chưa đo (ADAR) |
| Hành động nhạy cảm có ánh xạ quyền | 100% | chưa đo |
| Hành động ngoài quyền thành công (UASR) | 0 | chưa đo |
| Rò vai xuyên domain | 0 | chưa đo |
| Membership đã thu hồi vẫn ALLOW | 0 | chưa đo |
| Mã hành động biến DENY thành ALLOW | 0 | chưa đo |
| Quyền chưa ánh xạ mặc định ALLOW | 0 | chưa đo |
| Vai ứng dụng ghi được nguồn phân quyền hữu hiệu | 0 | **6/6 nguồn ghi được** |
| Sửa trạng thái phân quyền trái phép (UPMSR) | 0 | chưa đo |

### B. Cách ly — PostgreSQL / API

| Chỉ số | Đích | Hiện tại |
|---|---|---|
| Phân loại bảng tenant | 100% | 34/34 đã biết |
| Isolation protection coverage | 100% | **32/34 = 94,1%** |
| Bảng RLS có FORCE | 100% | **100%** |
| Hàng nhìn thấy khi không ngữ cảnh | 0 | đạt (fail-closed) |
| Rò đọc xuyên tenant | 0 | chưa đo |
| Ghi xuyên tenant thành công | 0 | chưa đo |
| Lạ ≈ không tồn tại | 100% ca | chưa đo |
| Giả mạo ngữ cảnh tenant qua API (TCBVR) | 0 | chưa đo |
| Vai ứng dụng SUPERUSER / BYPASSRLS | 0 | **0** |
| Bảng tenant mới chưa phân loại | 0 | **0** |

### Hai chỉ số tổng

```
SVSR = 0      (gộp A + B + C; CTIVR và UASR là hai thành phần của nó)
SMDR = 100%
```

### Ngoài phạm vi Mức I

| | |
|---|---|
| `voya_app` giả mạo được `app.tenant_id` | **giới hạn TCB / Mức II** |

Hàng này **không được ghi là pass**. Nếu luận văn chọn Mức I, nó được ghi đúng
tên: giới hạn của ranh giới tin cậy, kèm khai báo TCB đặt **trước** phần kết quả:

> Credential CSDL của ứng dụng và thành phần thiết lập ngữ cảnh tenant nằm trong
> trusted computing base. Hệ thống không tuyên bố chống được kịch bản credential
> đó bị chiếm hoàn toàn hoặc thực thi SQL tuỳ ý dưới credential đó.

---

## 8. Thứ tự thi công

Không lấy kết quả của bước 6–8 làm số chính thức trước khi bước 1–5 xong: hiện đã
biết trước một khiếm khuyết khiến kết quả không thể xanh, nên chạy bộ 500 bây giờ
chỉ cho một baseline đỏ đã đoán trước.

```
1. Xử lý `tenants`                      ← khoảng trống cách ly ĐANG SỐNG
      đường tenant thường chỉ thấy dòng của mình
      đường xuyên tenant/điều khiển thu hẹp rõ ràng
2. Chốt `tenant_purges`                 ← khoảng trống cách ly/điều khiển ĐANG SỐNG
      RLS, hoặc thu hồi quyền trực tiếp của vai ứng dụng + capability hẹp
3. Thu hẹp quyền trên 6 nguồn phân quyền hữu hiệu (§4.2)
      nguyên thuỷ leo thang đang NGỦ — thành CHÍ MẠNG ngay khi Casbin cưỡng chế
4. Làm sạch shadow mismatch  → ADAR = 100%
5. AUTHZ_MODE=casbin, test phân quyền có đích xanh
6. Dựng và chạy 500 thao tác đối kháng (A/B/C)
7. CTIVR = 0, UASR = 0, TCBVR = 0, UPMSR = 0
8. Bộ đột biến → SMDR = 100%
9. Toàn bộ suite = 0 fail
```

**Không được đảo bước 3 và bước 5.** Bật Casbin trước khi thu hồi quyền ghi lên
nguồn phân quyền sẽ tạo ra một vòng tin cậy khép kín:

```
voya_app sửa được thẩm quyền
      → thẩm quyền quyết định request của voya_app
```

Một hệ như vậy không bảo vệ được trước hội đồng, và cũng không bảo vệ được trước
kẻ tấn công.

Có thể viết harness của bước 6 song song với bước 1–3; chỉ đừng công bố số của nó.

### Ba cổng phát hành

**Gate A — hai bảng tenant đã đóng** (sau bước 1–2):

```
Isolation Protection Coverage        34/34 = 100%
voya_test_app ở tenant A
    SELECT tenants                   chỉ thấy A
    UPDATE tenant B                  0 dòng / bị từ chối
truy cập trực tiếp tenant_purges     đúng hợp đồng đã chọn
test xuyên tenant                    0 vi phạm
```

Chỉ khi đó mới được gọi là "table isolation coverage complete".

**Gate B — Casbin được phép bật** (trước `AUTHZ_MODE=casbin`):

```
App ghi được nguồn phân quyền        0
UPMSR                                0
ADAR                                 100%
Mismatch chưa giải quyết             0
Ánh xạ quyền cho hành động nhạy cảm  100%
Test phân quyền có đích              0 fail
```

**Gate C — luận văn được quyền nói "đạt Mức I"** (sau cutover):

```
AUTHZ_MODE                           casbin
UASR / CTIVR / TCBVR / UPMSR         0
Lạ ≈ không tồn tại                   100%
Isolation Protection Coverage        100%
FORCE where applicable               100%
App SUPERUSER / BYPASSRLS            0
SMDR                                 100%
Security / full-suite failures       0
```

Câu kết luận viết sẵn ở §9 chỉ được dùng khi Gate C xanh.

## 9. Điểm dừng

```
CASBIN
  AUTHZ_MODE                        casbin
  Unresolved shadow mismatch        0
  Sensitive action coverage         100%
  Unauthorized action success       0
  Cross-domain role leakage         0
  App writes to effective-authz     0
  UPMSR                             0

ISOLATION
  Tenant table classification       100%
  Isolation protection coverage     100%
  RLS FORCE where applicable        100%
  No-context leakage                0
  Cross-tenant read leakage         0
  Cross-tenant write success        0
  API tenant-context forgery        0
  Foreign-vs-nonexistent mismatch   0

PRIVILEGE
  App SUPERUSER                     0
  App BYPASSRLS                     0
  Unknown structural exceptions     0

VALIDATION
  CTIVR                             0
  SMDR                              100%
  Security test failures            0
  Full-suite failures               0
```

Khi toàn bộ xanh, chương kết quả mới được viết:

> Kết quả thực nghiệm xác nhận CTU.SignBridge đạt các tiêu chí Mức I trong threat
> model đã tuyên bố: Casbin cưỡng chế quyền hành động, PostgreSQL RLS và các ranh
> giới capability giới hạn phạm vi dữ liệu, và bộ kiểm đối kháng không ghi nhận
> thao tác trái quyền hay xuyên tenant nào thành công.

Nếu chọn Mức II thì lời khuyên đảo chiều: **ngừng vá GUC**. Ba hướng, khả thi
giảm dần:

1. **Capability function** suy tenant từ token đã xác thực thay vì đọc GUC; vai
   ứng dụng chỉ có `EXECUTE`, không `SELECT` trực tiếp trên bảng tenant.
2. **Vai CSDL theo tenant** — cách ly thật nhất, không khả thi ở quy mô SaaS.
3. **Gọi đúng tên là cách ly khuyến nghị** và đặt biên giới thật ở tầng khác.

Đây là hai mức nghiên cứu khác nhau; trộn chúng lại là cách chắc chắn để không
chứng minh trọn vẹn mức nào.

## 10. RLS dựa trên GUC: đủ cho Mức I, không đủ cho Mức II

Đây là phân biệt dễ bị đọc nhầm nhất trong cả tài liệu, và nếu để mơ hồ thì bước
1 của §8 (bật RLS cho `tenants`) trông như mâu thuẫn với lời khuyên "đừng xây
policy trên GUC".

Hai câu, và chúng không mâu thuẫn:

```
RLS + tenant GUC do thành phần TIN CẬY đặt   →  cưỡng chế hợp lệ cho MỨC I
RLS + tenant GUC do chính vai bị ràng buộc đặt  →  KHÔNG đủ cho MỨC II
```

Mức I đã chủ động đặt `voya_app` và thành phần thiết lập ngữ cảnh tenant **vào
trong TCB**. Trong threat model đó, chuỗi:

```
backend xác thực A → mã tin cậy đặt app.tenant_id = A
                   → truy vấn quên WHERE tenant_id
                   → RLS vẫn khoá về A
```

là một cơ chế cách ly hợp lệ, và nó đóng đúng khoảng trống *missing-filter* —
kiểu lỗi phổ biến nhất và tốn kém nhất trong một hệ đa tenant.

Vì vậy phát biểu đúng là: **không dùng RLS dựa trên GUC để tuyên bố đạt Mức II;
vẫn dùng nó để đóng khoảng trống missing-filter ở Mức I.** Bật RLS cho `tenants`
ở bước 1 là làm việc thứ hai, không phải việc thứ nhất.

Điều bị tạm dừng hẹp hơn nhiều so với "mọi refactor policy": đó là việc **thiết
kế lại kiến trúc tin cậy** trên nền GUC rồi tuyên bố đã tạo ra một biên giới bảo
mật chống được vai ứng dụng. Việc đó mới là việc không mua được gì.

## 11. Cách trình bày trong chương kết quả

Không biến chương kết quả thành danh sách tính năng bảo mật. Trình bày theo chuỗi
lập luận, vì chính chuỗi đó mới là đóng góp:

```
Threat model                    ai là kẻ tấn công, cái gì nằm trong TCB
      ↓
Security invariants             điều gì phải luôn đúng
      ↓
Mechanisms                      Casbin | RLS | đặc quyền CSDL
      ↓
Adversarial experiments         500 thao tác A/B/C, bộ đột biến
      ↓
Metrics                         ADAR · UASR · CTIVR · TCBVR · UPMSR · SMDR
      ↓
Result                          PASS/FAIL Mức I
      ↓
Limitation                      Mức II KHÔNG được tuyên bố
```

Chuỗi này chứng minh bốn điều nối tiếp nhau, và mỗi bước đều có số:

> cơ chế **tồn tại** → cơ chế **thực sự cưỡng chế** → bộ test **phát hiện được**
> khi cưỡng chế bị phá → hành vi đối kháng **không vượt** được biên giới trong
> threat model đã tuyên bố.

Đó là một luận điểm mạnh hơn hẳn "hệ thống dùng Casbin và PostgreSQL RLS nên an
toàn" — câu đó chỉ nói tới bước thứ nhất.

## 12. Ma trận truy cập

Hoàn thành ở mức **kiểm kê**: bảng nào hướng tenant, thao tác R/W, đường nào thật
sự xuyên tenant, đâu là mặt phẳng danh tính/điều khiển, bán kính ảnh hưởng.

Số đo đã có: trong 14 chỗ điều khiển, 10 thao tác trên một tenant được nêu tên
(`WHERE tenant_id = %s`), 4 thật sự xuyên tenant (liệt kê mọi tenant, `INSERT INTO
tenants`, liệt kê và tổng hợp mức dùng).
