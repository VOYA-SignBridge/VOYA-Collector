# P1 BẢO MẬT — vai ứng dụng tự cấp phép được `system_scope`

**Mở:** 15/08/2026 · **Trạng thái:** CHƯA VÁ · **Chặn:** deploy vòng 2, migration least-privilege, hai lớp vùng thật, QIPEDC

---

## 1. Số đo

```
voya_test_app / signdb_test      không sentinel  →  0 dòng
                                 tự đặt sentinel → 63 dòng, và UPDATE 63
voya_app      / signdb (SX)      không sentinel  →  0 dòng
                                 tự đặt sentinel → 63 dòng          (chỉ đọc)
```

Câu lệnh vai ứng dụng tự chạy được:

```sql
SELECT set_config('app.system_scope', 'on', false);
```

`app.system_scope` là GUC **tuỳ biến**, và PostgreSQL cho mọi vai tự đặt GUC
tuỳ biến. Không có bậc quyền nào ở đó. Chính sách RLS tin vào GUC ấy
(`rls.py:240`), nên vai ứng dụng tự mở được cánh cửa mà RLS dựng lên để chặn nó.

## 2. Phát biểu đúng về ranh giới hiện tại

```
tenant_scope + RLS        fail-closed khi mã QUÊN đặt tenant context
system_scope trên voya_app  năng lực ỨNG DỤNG được tin cậy
                            KHÔNG phải biên giới do CSDL cưỡng chế
```

Giá trị của RLS hôm nay là thật và đã được chứng minh: ba sự cố fail-open ở mặt
phẳng danh tính đều là loại "quên", và RLS bắt được. Nhưng nó **không** bảo vệ
trước một vai ứng dụng bị chiếm hoặc một đường thực thi SQL tuỳ ý.

Mức phơi nhiễm hôm nay hẹp — sản xuất có 2 tenant, 63 lớp đều thuộc `default` —
nhưng hướng đi là SaaS đa tenant.

## 3. Vì sao không vá được bằng `pg_has_role`

Thiết kế "sentinel = ý định, vai = năng lực" là đúng, nhưng không triển khai
được ở hình dạng hiện tại:

```
135 call site  ·  35 tệp  ·  TẤT CẢ chạy dưới voya_app
```

Cho `voya_app` làm thành viên vai năng lực thì lỗ nguyên si. Không cho thì 135
đường hợp lệ chết — trong đó có `auth.py` ("identity plane, runs before a tenant
is known"), `api_keys.py`, `access_gate.py`.

Với 135 đường system-scope hợp lệ trên chính vai ứng dụng, CSDL **không có cách
nào** phân biệt việc nền tảng chính đáng với việc vai ứng dụng tự tuyên bố.

## 4. Kiểm kê 135 call site — LƯỢT MỘT

> **Đây là phân loại sơ bộ, đọc từ chuỗi `reason` và ngữ nghĩa tệp.** Nó CHƯA
> trả lời được hai trong năm câu hỏi cần trả lời cho từng chỗ: *đọc hay ghi*, và
> *đụng bảng nào*. Con số dưới đây dùng để **định cỡ**, không dùng để kết luận.

| nhóm | nghĩa | số | tỉ lệ |
|---|---|---|---|
| **A** | tenant ĐÃ biết — `system_scope` là lối tắt → chuyển về `tenant_scope` | **42** | 31% |
| **B** | mặt phẳng danh tính thật (trước khi biết tenant) | **27** | 20% |
| **C** | việc nền tảng thật, xuyên tenant theo bản chất | **48** | 36% |
| **D** | CLI / bootstrap / bảo trì — kết nối riêng | **11** | 8% |
| — | cơ chế `tenant_context.py`, không tính | 5 | 4% |
| ? | chưa quy được, cần đọc mã | 2 | 1% |

### Nhóm A (42) — tenant được nêu tên ngay trong thao tác

| tệp | số | ví dụ |
|---|---|---|
| `tenant_admin.py` | 13 | *change the plan of a tenant*, *list members of a tenant*, *remove a member from a tenant* |
| `tenant_lifecycle.py` | 10 | *record an export request*, *list the exports of a tenant*, *preview a purge* |
| `subscription_lifecycle.py` | 8 | *dat ky han*, *doi trang thai thanh toan*, *vao an han* |
| `webhooks.py` | 4 | *register an endpoint for a tenant*, *list the endpoints of a tenant* |
| `api_keys.py` | 3 | *create a key for a tenant*, *revoke a key* |
| `plans.py` | 3 | *resolve the plan of a tenant*, *count {metric} of a tenant* |
| `usage.py` | 1 | *read the usage series of a tenant* |

Hình dạng đúng cho cả nhóm: quản trị viên nền tảng **hành động NHÂN DANH** một
tenant cụ thể. Năng lực đến từ tầng phân quyền; phạm vi CSDL thu về **đúng một
tenant** thay vì toàn bộ. Đây là phần giảm bề mặt lớn nhất và rẻ nhất.

### Nhóm B (27) — danh tính thật, trước khi biết tenant

`auth.py`, `access_gate.py`, `tenant_middleware.py`, `authorization/scope_resolver.py`
(4), `authorization/passcode.py` (5), `api_keys.py` *authenticate a caller by key*,
`tenant_admin.py` *resolve/accept an invitation* (2), `account_rename.py` (3),
`legal.py` phần chấp thuận **gắn với tài khoản, không gắn với tenant** (5), v.v.

Đây là nhóm buộc phải chạy trước khi tenant được xác định. **Nhưng nó không vì
thế mà cần quyền ghi lên mọi bảng tenant** — `auth.py` tra
`user → memberships → tenants` không có nghĩa nó cần `UPDATE classes` của mọi
tenant. Quyền của nhóm này phải hẹp **theo bảng**.

### Nhóm C (48) — việc nền tảng thật

`legal.py` văn bản nền tảng (15), `webhooks.py` hàng đợi giao (6),
`usage.py` tổng hợp xuyên tenant (4), `tenant_admin.py` *list every tenant* /
*create tenant* (4), `plans.py` bảng giá nền tảng (3), `audit.py` (2),
`platform_settings.py` (2), `worker.py` (2), và các mục lẻ.

Đây là mặt phẳng điều khiển. **Không được gộp chung vai với nhóm B.**

### Nhóm D (11) — CLI, bootstrap, bảo trì

`cli/legal_store.py` (4), `cli/verify_deployment.py` (3), bốn script backfill.
Chạy ngoài đường phục vụ yêu cầu, nên phải có kết nối riêng và **không được với
tới được từ đường yêu cầu của tenant**.

## 5. Điều con số này nói ra

Kỳ vọng ban đầu là "phần lớn 135 chỗ chỉ là lối tắt". **Không phải.** Chỉ ~31%
là lối tắt rõ ràng; ~56% (B+C) là công việc thật sự vượt phạm vi tenant.

Hệ quả cho thiết kế: một vai `voya_identity` gộp cả B và C sẽ trở thành một
super-role mới — đúng vấn đề cũ dưới tên khác. Kiến trúc đích cần **ba** mặt
phẳng tách biệt:

```
voya_app         mặt phẳng DỮ LIỆU tenant   — KHÔNG có năng lực system scope
voya_identity    mặt phẳng DANH TÍNH        — quyền hẹp THEO BẢNG, không blanket
voya_control     mặt phẳng ĐIỀU KHIỂN       — migration, bảo trì, việc nền tảng
                                              pool riêng, không với tới từ request
```

## 6. Thứ tự (đã chốt với chủ sở hữu)

1. Kiểm kê 135 chỗ ← **lượt một xong, tài liệu này**
2. Chuyển các lối tắt rõ ràng của nhóm A về `tenant_scope`
3. Phân loại phần còn lại bằng cách ĐỌC MÃ, không chỉ đọc `reason`
4. Thiết kế ranh giới credential/pool từ số đo thật
5. `voya_app` chỉ còn tenant — **mốc bảo mật**: app đặt sentinel vẫn 0 dòng
6. Tách kết nối danh tính / điều khiển
7. Lúc đó `pg_has_role(session_user, …)` trong RLS mới là năng lực thật
8. Sau khi ranh giới được chứng minh mới quay lại migration least-privilege,
   `required_postconditions`, SOT replay, deploy vòng 2

**Bước 2 là THU HẸP BỀ MẶT VÀ PHÂN LOẠI, không phải "đã vá bảo mật".** Khiếm
khuyết chỉ thực sự đóng khi vai ứng dụng hướng-tenant không còn bất kỳ
credential hay năng lực nào tự mở được phạm vi xuyên tenant.

## 7. Liên quan

- [ISSUE_runtime_schema_mutation.md](ISSUE_runtime_schema_mutation.md)
- [ISSUE_sot_reader_as_schema_migrator.md](ISSUE_sot_reader_as_schema_migrator.md)
- Migration least-privilege: backfill DML im lặng không chạy dưới vai không
  superuser (`UPDATE 0` với `voya_test_owner`, `UPDATE 63` với `admin`), rồi
  câu ràng buộc theo sau im lặng thất bại. Hợp đồng migration vì thế cần tập
  thứ ba: `required_postconditions`.
