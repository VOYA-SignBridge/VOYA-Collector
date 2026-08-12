# Phân quyền — PDM v5 + Casbin

> Trạng thái: **shadow mode**. Hệ cũ (`users.is_admin`, `tenant_members.role`)
> vẫn quyết định mọi request. Casbin chạy song song và ghi lại bất đồng.
>
> Lược đồ đã ở v5 (`memberships` + `role_assignments`); các router thì chưa —
> xem §13 và §14.

---

## 1. Bốn câu hỏi, bốn cơ chế

Đây là thứ dễ trộn lẫn nhất, nên nó đứng đầu tài liệu.

| Câu hỏi | Ai trả lời | Ở đâu |
|---|---|---|
| Dòng này ai được **chạm** tới? | Row-Level Security | `app/storage/rls.py` |
| Quan hệ này có được phép **tồn tại**? | Khoá ngoại ghép | `app/storage/authz_schema.py` |
| Chủ thể có **năng lực nghiệp vụ** này? | Casbin | `app/authorization/` |
| Đúng là **người này** đang ngồi đây? | Mã hành động | `app/authorization/passcode.py` |

Không cái nào thay được cái nào. Một người có thể qua RLS và khoá ngoại mà vẫn
bị Casbin từ chối, và ngược lại. Nhét cả bốn vào một chỗ là cách chắc chắn nhất
để mất cả bốn.

---

## 2. Mô hình dữ liệu

```
users ──── memberships ──── role_assignments ──── roles ──── role_permissions ──── permissions
              │                    │
              │                    └── membership_id NULL  ──► phạm vi HỆ THỐNG
              │
              ├── scope_level = 'TENANT'     (tenant_id)
              ├── scope_level = 'WORKSPACE'  (tenant_id, workspace_id)      cha: TENANT
              └── scope_level = 'PROJECT'    (+ project_id)                 cha: WORKSPACE

tenant_members  =  VIEW trên lát cắt scope_level = 'TENANT'   (cầu tạm, xem §13)
```

`tenants → workspaces → projects` là cây chứa dữ liệu; `memberships` là cây tư
cách thành viên; `role_assignments` là lịch sử cấp quyền.

**Một bảng gán, không phải bốn.** Phạm vi của một lần gán đọc từ `memberships`
mà nó trỏ tới, chứ không từ việc nó nằm ở bảng nào — xem §13.

### Khoá thay thế, không phải khoá tự nhiên

`role_assignments` dùng `assignment_id UUID` chứ không `(user, role)`. Lý do là
chuỗi **cấp → thu hồi → cấp lại**: với khoá tự nhiên, lần cấp thứ hai phải ghi
đè dòng cũ và lịch sử lần thu hồi biến mất.

### Ba cách một quyền chấm dứt

Bỏ sót bất kỳ cái nào đều để lại một đường cấp quyền sống dai. Adapter lọc cả ba:

| Cách | Cột | Dễ quên? |
|---|---|---|
| Thu hồi khỏi một người | `assignment.revoked_at` | không |
| Người rời khỏi tenant | `memberships.status`, `left_at` | **có** |
| Cả một role bị vô hiệu | `roles.is_active` | có |

Cái thứ hai là bẫy: gỡ mềm ai đó **không** tự thu hồi `role_assignments` của họ.
Không JOIN vào membership, người đã bị đuổi khỏi tổ chức vẫn giữ nguyên quyền
quản trị.

Cái thứ ba có **hai lớp**, và cần cả hai — xem bảng ở §12.

---

## 3. Thống trị phạm vi

```
SYSTEM  ⊃  TENANT  ⊃  WORKSPACE  ⊃  PROJECT
```

Quyền phạm vi PROJECT được hỏi lần lượt ở `prj:P → ws:W → ten:T → sys`. Vì vậy
một tenant admin xoá được mẫu trong mọi project **mà không cần assignment nào ở
project**.

Chiều ngược lại không tồn tại, và đó mới là phần quan trọng: quyền phạm vi
TENANT chỉ được hỏi ở `ten:T → sys`. Một `project_manager` không bao giờ chạm
được `tenant.billing.manage`.

Hai lớp cưỡng chế, độc lập:

* `build_domains()` không bao giờ đưa `prj:` vào chuỗi của một quyền TENANT.
* Trigger `ct_role_permissions_dominance` từ chối ngay việc xếp quyền TENANT
  vào một role PROJECT.

---

## 4. Casbin — và nó KHÔNG làm gì

Casbin trả lời đúng một câu: *chủ thể S có quyền P tại domain D không*.

Nó **không** chịu trách nhiệm cho: project thuộc đúng workspace, cách ly tenant
ở tầng dòng, tính bất biến của registry, số học hoá đơn, sổ kiểm toán chỉ-thêm.
Tất cả những thứ đó thuộc PostgreSQL.

### Không có bảng `casbin_rule`

PostgreSQL là **nguồn sự thật duy nhất**. Adapter (`app/authorization/adapter.py`)
chỉ *chiếu* các bảng RBAC thành policy trong bộ nhớ; mọi đường ghi ngược đều ném
`NotImplementedError`.

Nếu bỏ Casbin, dữ liệu quyền còn nguyên và thay được bằng engine khác mà không
migrate lại bảng nào.

### Domain chính tắc

```
sys                 hệ thống
ten:<tenant_id>     tenant
ws:<uuid>           workspace
prj:<uuid>          project
```

---

## 5. Trình tự một request

```
xác thực
   ↓
tư cách thành viên còn hiệu lực?     ← đọc từ NGUỒN THẬT, không từ cache
   ↓
Casbin: có quyền không?              ← DENY thì DỪNG
   ↓
quyền này đòi mã hành động?          ← chỉ chạy khi ĐÃ ALLOW
   ↓
giao dịch + SET LOCAL (RLS) + audit + outbox
```

**Mã hành động không bao giờ biến DENY thành ALLOW.** Đảo hai bước cuối sẽ tạo
ra một hệ thống mà nhập đúng mã thì làm được mọi thứ. Dùng
`passcode.require_step_up()` thay vì tự ghép hai bước.

---

## 6. Ba chế độ

`AUTHZ_MODE` trong `.env`:

| Giá trị | Ai quyết định | Nạp policy hỏng thì sao |
|---|---|---|
| `legacy` | `is_admin` + `tenant_members.role` | Casbin không chạy |
| `shadow` *(mặc định)* | hệ cũ | ghi log, không chặn request nào |
| `casbin` | Casbin | **tiến trình không khởi động** |

Đổi chế độ cần **force-recreate**, không phải `restart` — xem
`docs/INFRA_LIFECYCLE.md`.

### Điều kiện để rời shadow mode

Chỉ số Prometheus `voya_authz_shadow_mismatch_total`, tách theo `kind`:

| kind | Nghĩa | Bắt buộc |
|---|---|---|
| `deny_to_allow` | hệ cũ từ chối, Casbin cho qua → chuyển chế độ sẽ **mở rộng** quyền | **phải = 0** |
| `allow_to_deny` | hệ cũ cho qua, Casbin từ chối → thường là thiếu backfill | phải = 0 |
| `error` | không đánh giá được Casbin | phải = 0 |

`deny_to_allow` cũng ghi log ở mức ERROR với tiền tố `[AUTHZ-SHADOW][DENY->ALLOW]`.

Mismatch **không** đến từ khác biệt định nghĩa: `_legacy_decision` suy ra hệ cũ
từ chính các role dựng sẵn (`tenant_editor` *là* định nghĩa của
`tenant_members.role = 'editor'`). Nên mọi mismatch còn lại nhất định là khác
biệt về **dữ liệu** — assignment chưa backfill, membership lệch, role bị vô hiệu.

### Một mismatch đã biết trước — ĐÃ VÁ

`vocabulary_registry.tenant_role()` từng đọc `tenant_members` **không lọc theo
`status`**, nên một người bị gỡ mềm vẫn giữ nguyên quyền theo hệ cũ trong khi
Casbin từ chối họ. Nay hàm đó lọc `AND status = 'ACTIVE' AND removed_at IS NULL`
— **cùng vị từ** mà adapter dùng, và đó là điều kiện để hai vế so sánh được.

Lệch vị từ giữa hai bên sẽ làm shadow mode báo bất đồng cho một khác biệt do
chính hai truy vấn tạo ra. Nếu sửa một bên, phải sửa bên kia trong cùng lượt.

Cùng lượt đó vá một bẫy thứ hai: hàm này trả `str(rows[0]["role"])` vô điều
kiện, nên từ khi cột `role` nhận NULL, một thành viên không vai biến thành chuỗi
`"None"` — một vai không tồn tại, đi thẳng vào `LEGACY_TENANT_ROLE_MAP.get(...)`
và đẻ ra một dòng log ERROR ở **mỗi** request của người đó.

### Bẫy chờ sẵn cho ai làm luồng gỡ MỀM

`revoked_at` (vòng đời assignment) và `status`/`removed_at` (vòng đời
membership) là **hai đồng hồ độc lập**. Đo trên bản sao sản xuất 11/08:

| Bước | `memberships.status` | assignment `revoked_at IS NULL` | Casbin cấp quyền? |
|---|---|---|---|
| ban đầu | ACTIVE | 1 | có |
| gỡ mềm | REMOVED | **1 — vẫn còn** | **không** (adapter JOIN chặn) |
| thêm lại | ACTIVE | 1 | **có — quyền cũ SỐNG LẠI** |

Vế giữa an toàn: adapter JOIN vào membership nên không rò quyền lúc đang bị gỡ.

Vế cuối thì không: thêm lại một người **âm thầm khôi phục toàn bộ role cũ** của
họ, kể cả `tenant_admin`. Đó là một quyết định chính sách chưa ai ra.

Hôm nay đường này **không tới được**: `tenant_admin.remove_member` xoá CỨNG, và
`fk_role_assignments_membership` là `ON DELETE CASCADE` nên assignment đi theo.
Nó trở thành thật đúng vào ngày ai đó đổi `remove_member` sang
`UPDATE ... status = 'REMOVED'`.

> **Yêu cầu bắt buộc cho lần đổi đó:** thu hồi assignment trong **cùng giao
> dịch** với việc gỡ membership. Nếu không muốn phụ thuộc vào trí nhớ, cưỡng
> chế bằng trigger trên `memberships` — nhưng đừng nới `uq_*_active`, vì chỉ
> mục đó đang giữ đúng một bất biến khác.

### Tư cách thành viên CẮT chuỗi domain, không từ chối thẳng

Mất tư cách thành viên tenant loại bỏ `ten:` / `ws:` / `prj:` khỏi chuỗi nhưng
giữ `sys`. Người vận hành nền tảng thường **không** phải thành viên của tenant
họ đang xử lý (đình chỉ, xoá, hỗ trợ); từ chối thẳng sẽ làm mọi thao tác quản
trị trả 403 — kể cả trong shadow mode, nơi theo định nghĩa không kết quả nào
được phép đổi.

---

## 7. Triển khai

### Lần đầu

```bash
# 1. Schema + seed danh mục quyền: tự chạy trong ensure_tables() lúc khởi động.
#    Kiểm lại:
docker compose exec backend python -m app.cli.verify_deployment

# 2. Backfill quyền cũ sang RBAC mới. Chỉ báo cáo trước:
docker compose exec backend python -m app.cli.backfill_authz --actor <username>

# 3. Ghi thật:
docker compose exec backend python -m app.cli.backfill_authz --actor <username> --apply
```

`--actor` bắt buộc và không có mặc định: `assigned_by_user_id` là NOT NULL, và
ghi chính người được cấp vào đó sẽ tạo ra dòng kiểm toán nói *"tự cấp cho mình
quyền quản trị"* — sai về sự thật.

### Backfill làm gì

| Nguồn cũ | Đích |
|---|---|
| `users.is_admin = TRUE` | `role_assignments` (`membership_id` NULL) → `platform_administrator` |
| `tenant_members.role = 'admin'` | `role_assignments` (membership TENANT) → `tenant_administrator` |
| `tenant_members.role = 'editor'` | `role_assignments` (membership TENANT) → `tenant_editor` |
| `tenant_members.role IS NULL` | **không gán gì** — xem §12 |
| mỗi tenant | 1 workspace + 1 project mặc định, mọi thành viên vào cả hai |

**Không** gán role xuống workspace/project — thống trị phạm vi đã lo. Gán thừa
làm việc thu hồi phải nhớ bốn chỗ thay vì một.

Cột cũ được **giữ nguyên** trong suốt shadow mode: chúng là vế "cũ" của phép so
sánh, và xoá bây giờ là vứt đi thứ duy nhất chứng minh RBAC mới cho cùng kết quả.

### Chạy lại được

Mọi bước idempotent. Lượt thứ hai báo 0 thay đổi.

---

## 8. Lan truyền thay đổi policy

```
thay đổi RBAC  →  COMMIT  →  event_outbox('authorization.policy.changed')
                                     ↓
                    mỗi tiến trình API đọc mốc mỗi 20 giây
                                     ↓
                          reload_policy()  ← dựng lại TOÀN BỘ từ DB
```

Nạp lại toàn bộ chứ không vá từng dòng: trạng thái sau khi nạp chỉ phụ thuộc
vào cơ sở dữ liệu, không phụ thuộc vào việc mọi sự kiện trước đó đã được áp
đúng thứ tự. Một sự kiện bị mất chỉ làm policy cũ đi tới nhịp sau.

Với thao tác nhạy cảm (`ALWAYS_REVALIDATE` trong `authorization_service.py`),
tư cách thành viên được đọc thẳng cơ sở dữ liệu ở **mọi** request — không chờ
policy lan truyền.

> Worker webhook **phải bỏ qua** `event_type_code = 'authorization.policy.changed'`.
> Đó là tín hiệu nội bộ giữa các tiến trình API; gửi ra ngoài là rò cấu trúc
> quyền nội bộ vào webhook của khách hàng.

---

## 9. Dùng trong router

```python
from app.authorization import PERM, Target, require

@router.delete("/samples/{sample_uid}")
def delete_sample(sample_uid: str, current_user = Depends(get_current_user)):
    require(current_user, PERM.SAMPLE_DELETE, Target("sample", sample_uid))
    ...
```

Với quyền đòi mã hành động:

```python
from app.authorization.passcode import require_step_up

require_step_up(current_user, PERM.TENANT_PURGE,
                Target("tenant", tenant_id), passcode=body.passcode)
```

`PERM.X` là thuộc tính Python, không phải chuỗi: gõ sai thì `AttributeError`
ngay lúc import. Một chuỗi gõ sai tạo ra một quyền không ai có — endpoint đó từ
chối **tất cả mọi người**, kể cả quản trị viên nền tảng.

---

## 10. Chưa làm

Ghi ra để không ai tưởng đã xong.

* **Router chưa chuyển.** `is_admin` vẫn được đọc ở 12 tệp. Đó là Phase D và nó
  chỉ nên bắt đầu sau khi mismatch suite sạch.
* **Giao diện quản lý workspace/project/role.** Bảng đã có, API chưa. Phase 5.
* **`policy_invalidator.emit()` chưa có ai gọi.** Vì chưa có API nào thay đổi
  role — cách duy nhất để đổi quyền hôm nay là `backfill_authz` hoặc SQL trực
  tiếp, và cả hai đều đi kèm một lần khởi động lại. Cơ chế đã dựng và luồng nền
  đã chạy; API quản lý role đầu tiên phải gọi `emit()` trong **cùng giao dịch**
  với thay đổi, nếu không các tiến trình khác sẽ chạy policy cũ tới lần nạp sau.
* **`project_id` trên bảng dữ liệu.** `samples`, `classes`, `training_jobs` chưa
  mang cột đó, nên `scope_resolver._default_project()` trả về project mặc định
  của tenant. Đúng hôm nay (mỗi tenant đúng một project), sai vào ngày project
  thứ hai ra đời. `grep _default_project` để thấy toàn bộ chỗ còn nợ.
* **`RESOURCE_GRANT`.** Chia sẻ tài nguyên giữa các project (§15 PDM) chưa dựng.
* **Nạp policy theo tenant** (§21 Phase 2). Chưa cần: hiện tại toàn bộ policy
  vừa trong bộ nhớ mỗi tiến trình.

---

## 11. Tệp

| Tệp | Vai trò |
|---|---|
| `app/storage/authz_schema.py` | DDL, khoá ngoại ghép, trigger, `missing_objects()` |
| `app/authorization/catalog.py` | quyền nào tồn tại, role dựng sẵn gồm gì |
| `app/authorization/seed.py` | đối chiếu danh mục vào cơ sở dữ liệu |
| `app/authorization/adapter.py` | chiếu bảng RBAC → policy Casbin (chỉ đọc) |
| `app/authorization/enforcer.py` | vòng đời enforcer, hỏng-thì-đóng |
| `app/authorization/scope_resolver.py` | đối tượng nghiệp vụ → chuỗi domain |
| `app/authorization/authorization_service.py` | `authorize()` / `require()` |
| `app/authorization/passcode.py` | xác thực nâng cấp |
| `app/authorization/policy_invalidator.py` | outbox → nạp lại |
| `app/cli/backfill_authz.py` | dịch quyền cũ sang RBAC mới |
| `backend/tests/test_authorization.py` | ALLOW và DENY cho mỗi bất biến |

---

## 12. Tư cách thành viên ≠ vai

Đây là thay đổi mới nhất, và nó tách hai thứ vốn bị trộn từ đầu.

`tenant_members.role` nhận **ba** trạng thái:

| Giá trị | Nghĩa |
|---|---|
| `'admin'` | quản trị tenant |
| `'editor'` | biên tập dữ liệu và danh mục |
| `NULL` | **tư cách thành viên đang hoạt động, KHÔNG có authorization grant nào ở phạm vi tenant** |

### `NULL` KHÔNG có nghĩa "chỉ đọc"

Đây là phân biệt quan trọng nhất trong mục này. `NULL` là một phát biểu về
**authorization** — không có grant ở MỘT phạm vi — chứ không phải một phát biểu
về tập thao tác mà người đó làm được.

Gọi nhầm nó là "read-only" dẫn tới hai sai lầm ngược chiều nhau:

* Tưởng nó là một **mức quyền** → sẽ có người "hoàn thiện" nó bằng cách gắn
  thêm quyền đọc, và `tenant_viewer` mọc lại dưới một cái tên khác.
* Tưởng nó **cấm ghi vĩnh viễn** → sẽ có người dựa vào nó thay cho một phép
  kiểm quyền thật, rồi ngạc nhiên khi một grant ở workspace cho phép ghi.

Người mang `NULL` vẫn nhận được quyền — kể cả quyền ghi — qua assignment ở
**workspace/project** hoặc qua một **role tự tạo** của tổ chức. Những đường đó
đi qua Casbin và có hiệu lực thật khi `AUTHZ_MODE=casbin`.

### Nền tối thiểu của một thành viên không vai

Không phải con số không, và hai vế được cưỡng chế ở hai chỗ khác nhau:

| | Được gì | Cưỡng chế ở đâu |
|---|---|---|
| **Đọc** | Dữ liệu của tenant nhà, y như mọi thành viên khác | RLS. Không có phép kiểm vai nào trên đường đọc — một người trong tổ chức phải xem được tổ chức mình. |
| **Ghi** | CHỈ mặt phẳng tự phục vụ: tài khoản, mật khẩu, phiên, 2FA, xác minh, đồng thuận, chấp nhận điều khoản, phiếu hỗ trợ, thông báo của chính họ | `access_gate.SELF_SERVICE_WRITE_PREFIXES` — danh sách **cho phép**, mọi đường ghi khác bị từ chối |

Hai dòng trên là hợp đồng. Đổi một trong hai là đổi ý nghĩa của "không vai".

### Cổng chặn ở shadow mode, và vì sao nó phải tồn tại

`AUTHZ_MODE=shadow` nghĩa là Casbin chỉ **quan sát**; hệ cũ quyết định. Mà hệ cũ
chỉ biết đọc `tenant_members.role`, và **đúng hai chỗ** hỏi nó:
`routers/tenants.py::require_tenant_admin` và
`vocabulary_registry.assert_can_edit_registry`.

Mọi route ghi khác — thu mẫu, tải video, gửi huấn luyện, xoá bộ dữ liệu — không
hỏi vai gì cả. Không có cổng chặn, lời mời "không vai" đầu tiên sẽ tạo ra một
tài khoản ghi được gần như mọi thứ trong khi giao diện nói họ chưa có vai. Đó là
**fail-OPEN**, xuất hiện đúng lúc tính năng mới được bật.

Nên `access_gate` có một cổng thứ hai: phương thức đổi trạng thái + đường không
thuộc mặt phẳng tự phục vụ + không có grant nào → **403 `no_tenant_role`**.
Hỏng-thì-đóng: một lỗi khi tra cứu cũng là từ chối.

Cổng hỏi **"tài khoản này có grant ở tầng tenant ở BẤT KỲ đâu không"**, không
hỏi "trong tenant của request này". Middleware không biết request nói về tenant
nào — phần lớn đường ghi không nêu tenant nào cả, chúng ghi vào tenant nhà do
RLS quyết định. Bản đầu hỏi trong tenant nhà và chặn nhầm ngay ca phổ biến
nhất: quản trị viên của tenant B trong khi nhà ở tenant A. Phép kiểm THẬT ở
tầng router (`require_tenant_admin`) mới là chỗ biết B là B.

Cổng chặn **cả hai** trạng thái không-grant, và vế thứ hai là chủ ý:

| Trạng thái | Kết quả |
|---|---|
| có membership, `role IS NULL` | **403** |
| không có membership nào | **403** |

Vế thứ hai vượt ra ngoài "thành viên không vai", và nó được giữ vì ghi dữ liệu
vào một tenant mình không thuộc về là trạng thái mà chính mã nguồn gọi là
"không có hành vi đúng nào" (xem `tenant_admin.remove_member`). Sản xuất có **0**
tài khoản như vậy; 13 test từng dựa vào nó đã được sửa để dựng người dùng giống
thật, chứ không nới cổng ra cho test xanh.

Người vận hành nền tảng qua vì họ **CÓ quyền ở phạm vi SYSTEM** — đọc từ
`role_assignments (membership_id IS NULL)` hoặc từ `users.is_admin`, cách nói cũ
của cùng vai đó. Thiếu membership **không bao giờ** là lý do cho qua.

Cổng này là **hàng rào tạm**. Nó biến mất ở Phase D, khi các route đó gọi
`authorize()` và grant ở workspace/project mới thực sự dùng được.

### `tenant_viewer` đã nghỉ

Vai dựng sẵn `tenant_viewer` bị gỡ khỏi danh mục. Lý do không phải là nó trùng
với `workspace_viewer`/`project_viewer` — nó **không** trùng: 9 quyền đọc phạm
vi TENANT mà hai vai kia vĩnh viễn không cầm được. Lý do là nó gói bốn phép đọc
không hề hiền — `tenant.billing.read`, `tenant.audit.read`, `tenant.apikey.read`,
`consent.read` — vào một cái tên nghe như hiền, và tập quyền của nó do
`_read_only(TENANT)` sinh ra **theo hậu tố**, nên mọi quyền `.read` phạm vi
TENANT thêm sau này sẽ tự chảy vào mà không ai duyệt.

Chỉ-đọc toàn tenant vẫn làm được: Tenant Owner/Admin dựng một **role tự tạo**
từ các quyền mà nền tảng cho phép (`custom_role_allowed`). Khác biệt là ở đó có
người ký tên vào quyết định.

Đo trước khi gỡ (11/08/2026): **0 assignment**, 0 dòng `tenant_members` mang vai
`'viewer'`. Không ai bị thu hẹp quyền.

### Vai đã nghỉ: hai lớp, và cần cả hai

`catalog.RETIRED_BUILTIN_ROLES` liệt kê tường minh; `seed.py` đặt
`is_active = FALSE` cho những tên trong đó. Dòng `roles` và các dòng
`role_permissions` **ở lại** — chúng là câu trả lời duy nhất cho "vai này từng
cấp gì". Xoá hẳn là một migration riêng, sau khi xác minh mọi tham chiếu = 0.

Giữ lại grant chỉ an toàn nhờ hai lớp, và thiếu lớp nào cũng để lại một nửa lỗ:

| Lớp | Chặn gì | Thiếu nó thì sao |
|---|---|---|
| Trigger `ct_role_assignments_scope` | gán **mới** vào role đã tắt | giao diện cho gán một vai không bao giờ có hiệu lực; người dùng thấy "đã cấp", Casbin nói không |
| Bộ lọc `r.is_active` trong adapter | chiếu policy từ role đã tắt | vai đã nghỉ vẫn cấp quyền cho những người đã mang nó từ trước |

> `RETIRED_BUILTIN_ROLES` **viết tay**, không suy ra từ "role nào không có trong
> `BUILTIN_ROLES`". Vắng mặt có thể là GỠ HẲN hoặc mới chỉ ĐỔI TÊN, và một bước
> suy diễn tự động sẽ tắt `tenant_admin` cùng 4 assignment đang sống của nó, ở
> lượt khởi động kế tiếp, mà không ai yêu cầu.

### Mặc định của hai biểu mẫu

Cả **Mời** lẫn **Thêm thành viên** mặc định là **không vai**. Mặc định cũ là
`'viewer'`, nghĩa là bấm nút mà không đụng ô chọn vai đã cấp quyền đọc hoá đơn,
nhật ký kiểm toán, khoá API và đồng thuận — một quyết định phân quyền do một giá
trị mặc định đưa ra.

`_require_role()` nhận `None`, `""` và `"none"` như nhau. `"viewer"` thì **422**:
nó từng hợp lệ nên còn trong script của người ta, và dịch im lặng sẽ giấu mất
việc chỗ gọi đó cần sửa.

---

## 13. Cutover v5: một bảng gán, một bảng membership

Lượt này hoàn tất phần còn dở của v5. Trước nó, DDL đã dựng lược đồ v5 trong khi
bốn tệp vẫn nói ngôn ngữ v1.0 — nên chúng truy vấn những bảng **không còn được
tạo ra**.

| Cũ (v1.0) | Mới (v5) |
|---|---|
| `system_user_roles`, `tenant_member_roles`, `workspace_member_roles`, `project_member_roles` | `role_assignments` |
| `tenant_members`, `workspace_members`, `project_members` | `memberships` (+ view `tenant_members`) |

Phạm vi của một lần gán KHÔNG còn đọc từ việc nó nằm ở bảng nào, mà từ
`memberships` mà nó trỏ tới. `membership_id IS NULL` = phạm vi hệ thống, và
`ct_role_assignments_scope` cưỡng chế cả hai chiều.

Bốn chỗ đã chuyển: `authorization/adapter.py`, `cli/backfill_authz.py`,
`tenant_lifecycle.PURGE_ORDER`, `cli/verify_deployment.py`.

### `role_assignments` không nằm trong `PURGE_ORDER`

Có chủ ý: bảng đó không mang `tenant_id`, nên vòng lặp
`DELETE ... WHERE tenant_id = %s` không đụng tới nó được. Nó ra đi theo
`fk_role_assignments_membership` (ON DELETE CASCADE). Hệ quả cho thứ tự:
`roles` phải đứng **sau** `memberships`, vì `role_assignments.role_id -> roles`
là RESTRICT.

### `tenant_members` là VIEW, nên nó rời khỏi hai danh sách

Không gắn được khoá ngoại lên view, cũng không bật được RLS trên view. Giữ nó
trong `TENANT_SCOPED_TABLES`/`RLS_TABLES` làm `verify_deployment` báo FAIL vĩnh
viễn cho một thứ không bao giờ sửa được.

Bảo vệ chuyển xuống bảng nền `memberships`. Cái phải canh giờ là
**`security_invoker = true`** trên view: không có nó, view chạy dưới quyền chủ
sở hữu và RLS bị bỏ qua hoàn toàn — mọi tenant đọc được thành viên của mọi
tenant khác. Đó là fail-OPEN ở mặt phẳng danh tính, nên nó có test riêng
(`TestTheCompatibilityViewDoesNotBypassRls`) chứ không nấp trong một danh sách
bảng.

---

## 14. Community là một tenant dự trữ

Quyết định 12/08/2026, và nó **đảo** `COMMUNITY_DATA_COMMONS.md §10`.

Community được triển khai như tenant `community` với `tenant_type = 'COMMUNITY'`
và `is_system_reserved = TRUE`, kèm chỉ mục `uq_tenants_single_community` giữ
"đúng một". Lý do: là một tenant, nó thừa hưởng nguyên bốn lớp phòng thủ đã có
thay vì đòi một trục phân quyền song song với bốn cơ chế nhân đôi.

Ba điều kiện đi kèm quyết định đó, và cả ba đều có test:

1. **Không miễn trừ gì.** Community chịu đúng RLS, RBAC và cách ly tenant như
   mọi tenant khác. Không policy RLS nào được nhắc tên `community`.
2. **`is_system_reserved` là NHÃN, không phải QUYỀN.** Nó chỉ nói "đừng xoá
   tenant này". Không đường phân quyền nào được đọc nó — một test quét mã nguồn
   canh điều đó.
3. **Tư cách thành viên ≠ quyền.** Đây là rủi ro §10 cũ nêu, và cách chặn không
   phải là tránh làm Community thành tenant, mà là: không phép kiểm nào cho qua
   chỉ vì có membership. `community_member` — vai mọi tài khoản mới nhận — không
   được chứa quyền quản trị nào.

`community_member` và `community_curator` là role dựng sẵn phạm vi **TENANT**,
ghim vào `tenant_type = 'COMMUNITY'`. Chúng không phải một mức phạm vi thứ năm.

---

## 15. Cổng RLS: cách chạy lại, và vì sao phải chạy lại

`tenant_members` là VIEW (§13), nên thứ duy nhất giữ nó an toàn là
`security_invoker = true` trỏ ngược về `memberships`. Mất thuộc tính đó là
**fail-OPEN toàn bộ mặt phẳng danh tính**: mọi tenant đọc được thành viên của
mọi tenant khác, và không dòng log nào nói gì.

Nên cổng này phải chạy lại sau **mỗi** lần đụng vào `rls.py`, `authz_schema.py`,
hoặc định nghĩa view.

### Hai phép đo, và chỉ một cái là bằng chứng

| Đo cái gì | Bắt được gì | Không bắt được gì |
|---|---|---|
| Siêu dữ liệu (`reloptions`, `relforcerowsecurity`) | Thuộc tính bị mất | Vị từ policy viết sai |
| **Ghi thật rồi khẳng định bị TỪ CHỐI** | Cả hai | — |

Cả hai đều có trong bộ test. Cái thứ hai ở
`backend/tests/test_rls_write_gate.py`, và nó là cái đáng tin.

### Chạy

```bash
DB=$(grep '^DATABASE_URL=' .env | cut -d= -f2- | sed 's#/signdb#/authz_v5#')
MG=$(grep '^MIGRATION_DATABASE_URL=' .env | cut -d= -f2- | sed 's#/signdb#/authz_v5#')

docker run --rm --network voya-collector_voya_network \
  --env-file "$PWD/.env" \
  -e DATABASE_URL="$DB" -e MIGRATION_DATABASE_URL="$MG" \
  -v "$PWD:/src" -w /src voya_backend_test:latest \
  python -m pytest backend/tests/test_rls_write_gate.py -q
```

Bộ test chạy dưới `voya_app` (`NOSUPERUSER, NOBYPASSRLS`) vì `DATABASE_URL` trỏ
vai đó. **Đừng chạy cổng này dưới `admin`** — nó là superuser, bỏ qua RLS hoàn
toàn, và mọi ca sẽ "đạt" mà không đo gì. Đó là một cái bẫy đã sập một lần: một
lượt dò thủ công nối bằng `admin` và suýt kết luận rằng RLS chỉ để trang trí.

### Kết quả tham chiếu (12/08/2026, bản sao của sản xuất)

Đọc — dưới `voya_app`:

```
app.tenant_id=default    memberships (base)     30 trong / 0 NGOÀI
                         tenant_members (view)  10 trong / 0 NGOÀI
không đặt GUC nào        cả hai                  0
```

Ghi — 7/7:

| Ca | Kết quả |
|---|---|
| ghi vào chính tenant | cho phép |
| ghi chéo tenant | chặn |
| không có tenant context | chặn |
| `UPDATE` kéo dòng sang tenant khác | chặn |
| ghi chéo **qua view** | chặn |
| `app.system_scope = 'on'` | cho phép |
| `app.system_scope = '1'` (sentinel sai) | chặn |

Ca cuối đáng giữ: sentinel viết sai thì **fail-closed**. Nếu vị từ từng được
nới thành "khác rỗng thì coi như hệ thống", mọi giá trị rác sẽ mở toang cách ly
tenant — và không gì khác trong bộ test bắt được.

Ca `UPDATE` cũng đáng giữ riêng: `USING` và `WITH CHECK` là hai vị từ khác nhau.
Chỉ có `USING`, một dòng đọc được sẽ **sửa** được sang tenant khác — chuyển dữ
liệu qua ranh giới bằng UPDATE thay vì INSERT.

---

## 16. Lược đồ phân quyền đổi bằng LỆNH, không bằng lần khởi động

Từ 12/08/2026 thì `ensure_tables()` **không còn** chạy được phần một chiều của
mặt phẳng này. Cụ thể, năm câu sau chỉ chạy dưới `python -m app.cli.migrate`:

```
_DROP_VESTIGIAL_ROLE_NAME        bỏ cột roles.name
_MIGRATE_MEMBERSHIPS             chép tenant_members → memberships
_MIGRATE_ASSIGNMENTS             chép 4 bảng gán → role_assignments
_DROP_LEGACY_MEMBERSHIP_TABLES   bỏ 6 bảng cũ
_LEGACY_ROLE_RETIREMENT_DDL      'viewer' → NULL, rồi siết ràng buộc
```

Chúng gom trong `AUTHZ_ONE_WAY_DDL` — một **tập con** của
`AUTHZ_DDL_STATEMENTS`, không phải một danh sách thứ hai. Lý do nằm ở bốn ràng
buộc thứ tự ghi ngay trên `AUTHZ_DDL_STATEMENTS`: mỗi cái đổi lấy một lần hỏng
thật, và một danh sách thứ hai sẽ trôi khỏi thứ tự đó trong im lặng. Lọc phần
tử thì thứ tự tương đối giữ nguyên theo định nghĩa.

`_TENANT_MEMBERS_VIEW` **không** ở trong tập đó. `CREATE OR REPLACE VIEW` không
phá gì, và định nghĩa view đi theo mã chứ không theo dữ liệu — một ảnh mới phải
mang được định nghĩa view của chính nó lên mà không cần nghi thức migration.

**Hệ quả khi làm việc trên mặt phẳng này.** Thêm một bảng, một cột, một chỉ mục,
một chính sách RLS: cứ viết vào `AUTHZ_DDL_STATEMENTS`, khởi động sẽ tự cài.
Nhưng nếu câu mới bỏ đi thứ gì hoặc viết đè dữ liệu cũ, phải thêm nó vào
`AUTHZ_ONE_WAY_DDL` — nếu quên,
`test_no_irreversible_statement_survives_the_filter` sẽ đỏ và nói ra đúng câu
nào.

Toàn bộ lý lẽ, số đo và bảy ca kiểm chứng nằm ở
[INCIDENT_2026-08-12_schema_code_skew.md §6](INCIDENT_2026-08-12_schema_code_skew.md).

---

## 17. Chưa làm — sau lượt này

* **Router chưa chuyển.** `is_admin` vẫn đọc ở 12 tệp; các route ghi vẫn không
  gọi `authorize()`. Đó là Phase D, và nó là điều kiện để gỡ cổng chặn ở §12.
* **Grant workspace/project chưa dùng được thật.** Lược đồ và adapter đã sẵn
  sàng, nhưng chừng nào còn shadow mode thì hệ cũ quyết định, và hệ cũ không
  biết hai mức đó. Một người không vai tenant nhưng có grant project sẽ hiện ra
  dưới dạng `deny_to_allow` — mismatch THẬT, và phải giải quyết trước khi đổi
  `AUTHZ_MODE`.
* **Giao diện quản lý role.** Chưa có API nào tạo/thu hồi assignment, nên
  `policy_invalidator.emit()` vẫn chưa có ai gọi.
* **`project_id` trên bảng dữ liệu.** `grep _default_project` để thấy nợ.
