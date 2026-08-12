# Cô lập tenant — tham chiếu kỹ thuật

**Phạm vi:** A2 (role không-superuser) + A3 (row-level security + tenant context)
**Trạng thái:** đã hiện thực, đã chứng minh bằng test; xem [BACKEND_WORK_PROGRESS.md](BACKEND_WORK_PROGRESS.md) §9 cho nhật ký triển khai
**Thiết kế dài hạn:** [MULTITENANT_ARCHITECTURE.md](MULTITENANT_ARCHITECTURE.md) — tài liệu này chỉ mô tả phần **đã chạy**

---

## 1. Khẳng định trung tâm

> Một truy vấn không khai báo tenant trả về **0 hàng**, không phải mọi hàng. Và ứng dụng
> **không tự tắt được** cơ chế đó.

Hai nửa đều bắt buộc. Nửa đầu không có nửa sau chỉ là một quy ước lập trình.

Trước A2/A3, `tenant_id` có mặt trên 12 bảng kèm khoá ngoại đầy đủ, nhưng nó là **một cột
metadata**: mọi truy vấn quên `WHERE tenant_id` đều trả về dữ liệu của mọi tenant và không
gì báo lỗi. Ba hàm trong `storage/metadata_db.py` — `delete_sample()`,
`delete_samples_by_class()`, `update_sample_gdrive_url()` — đến hôm nay vẫn không lọc
tenant. Chính chúng là lý lẽ mạnh nhất cho việc đặt ranh giới ở tầng CSDL: vá chúng bằng
tay là vá ba hàm đã biết; policy vá luôn cả những hàm sẽ được viết sau này mà tác giả quên
lọc.

---

## 2. Hai role, và vì sao phải tách

| | `DATABASE_URL` | `MIGRATION_DATABASE_URL` |
|---|---|---|
| Role | `voya_app` | `admin` (superuser) |
| Quyền | SELECT/INSERT/UPDATE/DELETE | DDL |
| Dùng ở | mọi truy vấn lúc chạy | `ensure_tables()`, SOT apply schema, `provision_db_roles` |
| Cấp bởi | `python -m app.cli.provision_db_roles` | có sẵn |

**Vì sao không dùng một role.** `ALTER TABLE x DISABLE ROW LEVEL SECURITY` là DDL. Một role
vừa ghi được dữ liệu vừa chạy được DDL thì **tự gỡ được vòng vây của chính nó** — bảo đảm
đó trở thành lời khuyên, không phải bảo đảm.

**Vì sao `FORCE ROW LEVEL SECURITY` không đủ.** PostgreSQL miễn trừ RLS **vô điều kiện** cho
SUPERUSER và BYPASSRLS. `FORCE` chỉ gỡ miễn trừ của **chủ bảng**, không đụng tới miễn trừ
của superuser. Đây là cái bẫy chính:

```
Cài policy trong khi app vẫn nối bằng `admin`:
  pg_policies             -> đủ policy       ✓
  pg_tables.rowsecurity   -> true            ✓
  hành vi thật            -> mọi tenant       ✗
```

Mọi cách kiểm "nhìn vào cấu hình" đều báo xanh còn hành vi thật bằng không. Trạng thái này
**tệ hơn không làm RLS**, vì nó biến một khoảng trống đã biết thành một khẳng định sai. Đó
là lý do `assert_isolation_enforceable()` tồn tại và vì sao nó được gọi ở boot.

---

## 3. Hai GUC

| GUC | Ý nghĩa | Ai đặt |
|---|---|---|
| `app.tenant_id` | tenant mà transaction đang thay mặt | middleware HTTP |
| `app.system_scope` | `'on'` = việc của nền tảng, xuyên mọi tenant | boot, Celery, CLI, 1 endpoint admin |

Policy trên cả ba bảng:

```sql
USING      (current_setting('app.system_scope', true) = 'on'
            OR tenant_id = current_setting('app.tenant_id', true))
WITH CHECK (cùng biểu thức)
```

Bốn quyết định đóng gói trong bốn dòng đó:

1. **`current_setting(..., true)`** — dạng *missing_ok*, trả `NULL` thay vì raise khi GUC
   chưa đặt. `tenant_id = NULL` cho `NULL`, `NULL` không phải `TRUE` → **0 hàng**. Dạng
   raise sẽ ồn ào hơn nhưng kéo sập mọi truy vấn không liên quan trên cùng kết nối.
2. **`USING` và `WITH CHECK` giống hệt nhau.** `USING` quyết hàng nào *nhìn thấy được*,
   `WITH CHECK` quyết hàng nào *được sinh ra*. Khác nhau thì tenant hoặc ghi được hàng nó
   không đọc lại được, hoặc đẩy được hàng sang tenant khác.
3. **`system_scope` là GUC RIÊNG, không phải một tên tenant dành riêng.** `'on'` là một
   `tenant_id` hợp lệ theo `is_valid_tenant_id`; nếu quyền xuyên-tenant được biểu diễn bằng
   `tenant_id = 'on'` thì một tenant tên `on` — hoặc một lỗi gõ ra đúng chuỗi đó — sẽ âm
   thầm có quyền đọc chéo.
4. **`FORCE`** — để chủ bảng (role migration) cũng chịu policy.

---

## 4. Luồng nghiệp vụ: scope đi từ đâu tới đâu

### 4.1 Request HTTP

```
Request
  └─ TenantScopeMiddleware  (ASGI thuần, KHÔNG phải BaseHTTPMiddleware)
       ├─ đọc cookie voya_access, rồi tới Authorization: Bearer
       ├─ _subject_of(token) -> user_id      (không raise; token hỏng = ẩn danh)
       ├─ SELECT tenant_id FROM users WHERE id = ...   (users KHÔNG có policy → không vòng lặp)
       ├─ ẩn danh  -> settings.public_tenant_id
       └─ bind_request_scope(tenant)   [ContextVar]
            │
            └─ route + dependency + service
                 └─ metadata_db._cursor() / _fetch_all()
                      └─ apply_scope(cur)   →  SELECT set_config('app.tenant_id', <tenant>, true)
                           └─ câu truy vấn thật
```

**Middleware quyết *phạm vi*, dependency quyết *quyền truy cập*.** Middleware không bao giờ
từ chối request và không bao giờ raise: token hết hạn/giả mạo chỉ đơn giản là "không có
người dùng", và `Depends(get_current_user)` của route vẫn trả 401 y như trước. Nhờ vậy việc
thêm tenant scope **không thể** thay đổi hành vi xác thực của bất kỳ endpoint nào.

**Vì sao ASGI thuần.** `@app.middleware("http")` là `BaseHTTPMiddleware`, chạy ứng dụng phía
dưới trong một task nó tự sinh. Truyền context qua ranh giới đó là nguồn lỗi tinh vi đã
biết, mà giá trị đang truyền ở đây lại quyết định *dữ liệu của tenant nào được trả về* —
chỗ duy nhất mà "thường thì chạy đúng" là không đủ.

**Không header/query nào chọn được tenant.** Tôn trọng một `X-Tenant-Id` do client gửi sẽ
biến ranh giới cô lập thành một trường của request.

**Chi phí.** Request **ẩn danh không tốn truy vấn nào**: không có token thì hàm thoát trước
khi chạm DB. Nên `/health` và `/metrics` — hai đường bị scrape dày nhất — không phải trả gì,
và không cần allowlist đường dẫn nào để đạt điều đó. Chỉ request đã đăng nhập mới tốn thêm
một lần đọc chỉ mục.

### 4.2 Celery

```
task_prerun  -> enter_system_scope(f"celery:{task.name}")
   <task body>
task_postrun -> clear_scope()          (Celery đảm bảo chạy cả khi task raise)
```

Đặt ở signal chứ không ở từng task, để một task viết sau **không thể quên**. Hệ quả cần
biết: **Celery hiện không đóng vai một tenant cụ thể được**; tenant của một hàng do dữ liệu
của chính hàng đó quyết định, không do scope. Task nào cần hẹp hơn thì tự mở
`tenant_scope(...)` trong thân — đó là thu hẹp, không phải nới rộng.

### 4.3 Boot

`init_db()` là vỏ mỏng bọc `_init_db()` trong `system_scope`. Không có nó:
`_existing_keys()` đọc ra 0 hàng → kết luận DB rỗng → **re-upsert 3.860 hàng mỗi lần
boot**. Không mất dữ liệu (`ON CONFLICT DO UPDATE` giữ `deleted_at`), nhưng là một quả mìn
hiệu năng và một nguồn hoang mang khi đọc log.

### 4.4 CLI và SOT

`@platform_command("...")` trên `main()`. SOT là hiện vật **xuyên tenant theo định nghĩa**:
`publish` đọc hàng của mọi tenant ra, `sync` ghi hàng của mọi tenant vào. Không có scope,
`publish` sẽ xuất một catalogue rỗng và `sync` bị policy từ chối — cả hai đều **im lặng**,
vì mỗi bên đều đã dung thứ lỗi ở mức từng câu lệnh.

### 4.5 Kiểm kê đầy đủ nơi vượt ranh giới

`grep -rn "system_scope(" backend/app` phải chỉ ra đúng các chỗ sau:

| Nơi | Lý do |
|---|---|
| `db.init_db` | sync CSV→DB mang hàng của mọi tenant |
| `worker.task_prerun` | mọi task là việc nền tảng |
| `sot/cli.main` | SOT là hiện vật xuyên tenant |
| `cli/backfill_sample_owners.main` | lệnh vận hành |
| `cli/verify_deployment.main` | lệnh vận hành |
| `routers/sot_admin._db_counts` | **endpoint HTTP duy nhất**: đếm để so với snapshot SOT (là tổng xuyên tenant) |
| `tests/conftest._platform_scope` | suite chạy như tác nhân nền tảng |

`system_scope` **bắt buộc có tham số `reason`**. Không phải trang trí: đây là cấu trúc duy
nhất bước ra ngoài bảo đảm cô lập, và một `system_scope()` trần ở call site không nói cho
người review biết nó có chính đáng hay không.

---

## 5. Vì sao `SET LOCAL`, không phải `SET`

Kết nối đến từ `ThreadedConnectionPool` dùng chung. `SET` **bám lại** trên kết nối sau khi
trả về pool, nên request kế tiếp mượn đúng kết nối đó — có thể của tenant khác — thừa hưởng
ngữ cảnh cũ. `SET LOCAL` (ở đây là `set_config(..., true)`) chết theo commit/rollback.

Đây là lỗi kinh điển của RLS + connection pooling và **nó không tạo ra lỗi nào nhìn thấy
được**: chỉ đúng một người dùng xui xẻo đọc nhầm dữ liệu của người khác.

Dùng `set_config()` chứ không dùng cú pháp `SET LOCAL app.tenant_id = 'x'` vì cú pháp literal
**không nhận tham số bind** — sẽ phải nội suy tenant id vào chuỗi SQL ở mọi request.

Cả hai GUC đều được ghi mỗi lần, trong **một** câu lệnh, dù setting transaction-scoped không
thể sống sót qua transaction. Không tốn thêm round trip, và nó khiến scope của một
transaction được quyết định trọn vẹn bởi một lời gọi thay vì một phần bởi người mượn kết
nối trước đó.

**Chi phí:** một round trip thêm cho mỗi transaction. Đường upload chạy hàng trăm
transaction cho một video, tức thêm vài chục ms. Đã chấp nhận có ý thức: tính đúng đắn
trước, và nếu cần thì tối ưu bằng cách gộp transaction chứ không bằng cách bỏ scope.

---

## 6. Chính sách: request ẩn danh đọc tenant nào

`settings.public_tenant_id` (env `PUBLIC_TENANT_ID`, mặc định `default`).

Một số endpoint catalogue **cố ý công khai** — trang duyệt nhãn và demo realtime đọc
`classes`/`samples` không cần phiên. Dưới RLS, request không scope thì không thấy gì, nên
những trang đó sẽ trắng. Gắn traffic ẩn danh vào **một tenant có tên** giữ chúng chạy được
mà mọi tenant khác vẫn không thể chạm tới nếu không đăng nhập.

Đây là **một chính sách, không phải một fallback**: nó là tenant duy nhất có catalogue công
khai. Đặt rỗng thì request ẩn danh không thấy gì — cấu hình đúng cho một triển khai không có
catalogue công khai.

---

## 7. Bộ chứng minh

`backend/tests/test_tenant_isolation.py` — 38 test.

**Chạy trên một database dùng-một-lần.** Chứng minh cô lập cần một tenant thứ hai có hàng
thật trong `samples`/`classes`/`raw_uploads`. Ghi chúng vào database đang chạy là không chấp
nhận được: một Celery beat đối soát hàng active của Postgres ngược vào
`dataset/samples.csv` mỗi 5 phút, nên fixture của test có thể bị chép vào **nguồn sự thật**
và sau đó phải publish một phiên bản SOT mới mới gỡ được.

Nên: tạo database mới cho mỗi lần chạy, dựng bằng **DDL thật** (`metadata_db.DDL_STATEMENTS`)
và **policy thật** (`rls.rls_ddl()`), rồi xoá. Không có gì ở đây dựng lại schema hay policy
bản sao.

**Nối bằng `voya_app`, không phải `admin`.** Chạy bằng `admin` thì mọi assert bên dưới đều
xanh vì lý do sai — hàng nhìn thấy được, và "cô lập" chính là mệnh đề `WHERE` của test.
Fixture `app_conn` **fail** (không phải skip) nếu kết nối proof có thể bypass RLS.

| Nhóm | Khẳng định |
|---|---|
| Đọc | A chỉ thấy hàng của A (3 bảng); tra đúng khoá chính của B → không có gì; `COUNT(*)` không rò tổng; system scope thấy cả hai |
| Fail-closed | không scope → 0 hàng; **chưa từng gọi `set_config`** → 0 hàng; INSERT không scope bị từ chối; `''` không phải wildcard; `system_scope` phải đúng `'on'` (`ON`/`true`/`1`/`yes`/`" on"` đều không mở) |
| Ghi | UPDATE/DELETE chéo tenant đổi 0 hàng; `DELETE FROM samples` **không WHERE** chỉ xoá được tenant hiện tại; không INSERT được hàng mang tenant khác; không UPDATE để **chuyển** hàng sang tenant khác; **đối chứng âm**: INSERT vào chính tenant mình vẫn chạy |
| Role | không DISABLE được RLS, không DROP được policy, không CREATE TABLE |
| Tầng ứng dụng | `apply_scope` đọc đúng ContextVar; SQL là transaction-local; **cả `_cursor` lẫn `_fetch_all` đều thật sự gọi `apply_scope`** (quan sát lời gọi, không assert lên văn bản nguồn) |
| Phân giải tenant của request | cookie thắng Bearer; ẩn danh → tenant công khai; `public_tenant_id` rỗng → không scope; token hỏng / DB chết / tài khoản đã khoá đều **suy biến về ẩn danh, không raise**; id sai dạng không tới được GUC; **không header nào chọn được tenant** |
| Kiểm kê ranh giới | `system_scope` chỉ xuất hiện ở 7 file trong allowlist; **đúng một router** (`sot_admin`) được phép vượt |

### 7.1 Kiểm chứng bằng đột biến

Phá từng thứ bộ test tuyên bố bảo vệ (`scratchpad/mutate_rls.py`, tự khôi phục file):

| # | Đột biến | Kết quả |
|---|---|---|
| M1 | predicate luôn `true` (fail **open**) | CAUGHT |
| M2 | bỏ `WITH CHECK` | CAUGHT |
| M3 | `current_setting` bỏ `missing_ok` | CAUGHT |
| M4 | bỏ `FORCE ROW LEVEL SECURITY` | CAUGHT |
| M5 | `apply_scope` thành no-op | CAUGHT |
| M6 | `set_config(..., false)` — tức `SET` thay vì `SET LOCAL` | CAUGHT |
| M7 | tắt phân vùng lưu trữ (A4) | CAUGHT |
| M8 | bỏ chủ sở hữu khi đọc lớp từ một dòng dữ liệu (A4) | CAUGHT |
| M9 | chặn checkpoint bằng so khớp chuỗi thay vì `resolve()` (B1) | CAUGHT |
| M10 | hạn mức luôn khoá theo IP (B3) | CAUGHT |
| M11 | `--check` soi DSN migration thay vì DSN runtime | CAUGHT |

**11/11 bị bắt.** Điều này *không* có nghĩa là không còn lỗi; nó nói: mười một cách hỏng cụ
thể mà tôi nghĩ ra đều bị bắt.

M11 khác mười cái kia ở một điểm đáng ghi: nó **không phải giả định**. Đó là một lỗi có
thật, do tôi viết, và nó chỉ lộ ra khi chạy `--check` trên hệ đã triển khai thật — bộ test
lúc đó không hề chạm tới nhánh `--check`. Bài học không phải "cần thêm test", mà: **một
công cụ chẩn đoán cũng là mã sản xuất và phải bị đột biến như mọi mã khác**; nếu nó không
bao giờ có thể báo "xanh", không ai phát hiện được rằng nó chưa từng đo cái nó nói là đang
đo.

**Kết quả suite:** 1.030 qua · 0 hỏng · 0 skip (12 phút), chạy với `DATABASE_URL` trỏ role
**bị giới hạn**. Chạy bằng `admin` thì mọi khẳng định cô lập ở trên đều xanh vì lý do sai.
Lệnh chạy đầy đủ — thiếu một mảnh là đỏ giả hoặc skip giả — ghi ở
`BACKEND_WORK_PROGRESS.md` §9.10.

---

## 8. Vận hành

```bash
# cấp role (idempotent, chạy lại được để xoay mật khẩu)
VOYA_APP_DB_PASSWORD=... python -m app.cli.provision_db_roles

# soi tư thế, không đổi gì
python -m app.cli.provision_db_roles --check
```

`--check` mở **hai** kết nối và báo cáo cả hai, vì hai role có kỳ vọng ngược nhau và chỉ một
bên là phát hiện thật:

| DSN | Kỳ vọng | Nếu sai |
|---|---|---|
| `DATABASE_URL` (runtime) | **KHÔNG** được bypass RLS | exit 3 — cô lập chỉ là sân khấu |
| `MIGRATION_DATABASE_URL` | *phải* là superuser | không phải lỗi — nó cần thế để chạy DDL |

`--check` cũng exit 3 khi **không bảng nào** bật RLS: một role bị giới hạn trên cơ sở dữ liệu
không có policy thì cũng không được cô lập, nó chỉ không nhìn thấy sự khác biệt.

> **Bản đầu của `--check` sai và đã bị bắt lúc triển khai thật (2026-08-07).** Nó chỉ mở
> `connect_migration()` — vì *cấp phát* role cần superuser — rồi báo cáo tư thế của đúng
> kết nối đó. Kết quả: trên một hệ đã cutover **hoàn toàn đúng**, nó vẫn in
> `connected as: admin / superuser: True / WARNING: policies are theatre` và exit 0.
> Một cảnh báo không bao giờ tắt được thì tệ hơn không có cảnh báo: nó dạy người vận hành
> bỏ qua đúng dòng chữ quan trọng nhất. Ba test trong `TestCheckCommand` ghìm cả hai nửa
> (superuser ở role migration **không** phải phát hiện; superuser ở role runtime **là**
> phát hiện), và đột biến M11 khôi phục lại bug này để chứng minh test bắt được.

**Trình tự cutover (thứ tự này bắt buộc). Cú pháp PowerShell — host này là Windows:**

```powershell
# 1. Tạo role. Chưa đổi gì ở app.
$env:VOYA_APP_DB_PASSWORD="..."; python -m app.cli.provision_db_roles

# 2. Chạy TRỌN BỘ suite với DATABASE_URL trỏ voya_app.
#    Thiếu một GRANT thì lỗi xuất hiện LÚC CHẠY, trên một endpoint, chứ không
#    phải lúc khởi động — nên không được đổi rồi hy vọng.

# 3. Đổi .env: DATABASE_URL -> voya_app  VÀ  DB_STRICT_ISOLATION=1 (cùng lúc)

# 4. Rebuild + recreate. Mã backend được nướng vào image nên phải BUILD, và
#    .env chỉ được đọc lại khi FORCE-RECREATE (restart không đủ).
#    BA cờ -f phải viết THẲNG trong lệnh — xem cảnh báo bên dưới.
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.gpu.yml build backend
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.gpu.yml up -d

# 5. Xác minh
docker compose -f docker-compose.yml -f docker-compose.prod.yml -f docker-compose.gpu.yml `
    exec backend python -m app.cli.provision_db_roles --check
#    -> "runtime role: voya_app", superuser False, "OK: tenant isolation is in force", exit 0
docker ps   # 13 healthy + sot_init exited(0)
docker inspect voya_trainer --format "{{json .HostConfig.DeviceRequests}} {{.HostConfig.Memory}}"
#    -> KHÔNG được là "null 0"
```

> **Đừng gom ba cờ `-f` vào một biến shell.** Dòng bash
> `COMPOSE="-f docker-compose.yml -f ..."` chạy trên PowerShell sẽ **lỗi**
> (`CommandNotFoundException`), `$COMPOSE` rỗng, và dòng kế tiếp
> `docker compose $COMPOSE up -d` vẫn **thành công** — với **mỗi file base**.
> Hỏng lặng lẽ: container báo healthy nên không có gì cho biết `mem_limit` và device GPU
> đã bị rơi. Đây là lần tái diễn thứ hai của cùng một lỗi triển khai.

**Rollback** là đổi lại một dòng `DATABASE_URL` + `DB_STRICT_ISOLATION=0`; role `admin` vẫn
còn nguyên, policy vẫn cài nhưng vô hiệu với superuser.

**Trạng thái đã triển khai (2026-08-07):** 13 container healthy + `sot_init` exited(0);
`--check` exit 0; log khởi động của cả 4 gunicorn worker in
`[RLS] tenant isolation in force: role=voya_app tables=classes,raw_uploads,samples`;
`samples` vẫn đủ 3.860 hàng, toàn bộ `tenant_id='default'`. Đối chứng chạy trực tiếp trong
container: scope `default` → 3.860 hàng, scope một tenant không tồn tại → **0 hàng**,
`system_scope` → 3.860 hàng, và `ALTER TABLE samples DISABLE ROW LEVEL SECURITY` bị từ chối
(`InsufficientPrivilege: must be owner of table samples`) — cô lập không tự thu hồi được.

---

## 9. Điều tài liệu này *không* khẳng định

- **Không khẳng định mọi bảng đều được cô lập.** Đúng **ba** bảng có policy:
  `samples`, `classes`, `raw_uploads`. Chín bảng còn lại mang `tenant_id` vẫn chỉ có cột.
  Ba bảng chứng minh được bằng đối chứng âm đáng giá hơn mười hai bảng khai suông.
- **Cô lập ở tầng lưu trữ (A4) đã làm, nhưng chưa có dữ liệu thật kiểm chứng.** Tenant khác
  `default` ghi vào `FEATURES_ROOT/_tenants/<tenant>/`. Hôm nay hệ thống chỉ có đúng một
  tenant, nên nhánh đó mới chỉ được chứng minh bằng test và bằng đột biến M7, chưa bằng
  một tenant thứ hai chạy thật.
- **Không khẳng định Celery cô lập theo tenant.** Task chạy ở system scope; tenant của một
  hàng đến từ dữ liệu của hàng đó. Truyền tenant vào task là việc còn nợ.
- **Không khẳng định phòng được người trong cuộc có quyền DB.** Ai có `MIGRATION_DATABASE_URL`
  hoặc quyền superuser thì bỏ qua được toàn bộ. Ranh giới này chống lỗi lập trình và chống
  request chéo tenant, không chống người vận hành.
