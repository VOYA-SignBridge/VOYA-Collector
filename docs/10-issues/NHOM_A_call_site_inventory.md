# Kiểm kê call site Nhóm A — ĐÃ ĐỌC MÃ XONG

*15/08/2026. Bổ sung cho `ISSUE_app_role_self_authorizes_system_scope.md` §4. Toàn bộ 68 chỗ `system_scope` trong 7 tệp Nhóm A đã được đọc.*

| ký hiệu | nghĩa |
|---|---|
| **A** | tenant đã trong tay → chuyển thẳng sang `tenant_scope` |
| **A!** | chuyển được, nhưng phải TÁCH một bước danh tính ra trước |
| **N** | tra hẹp bắt buộc: khoá thay thế, tenant chỉ biết SAU lượt đọc này |
| **C** | xuyên tenant thật, giữ `system_scope` |
| **B** | mặt phẳng danh tính, chạy trước khi biết tenant |

| tệp | dòng | R/W | lý do | bảng | nhóm | căn cứ |
|---|---|---|---|---|---|---|
| `tenant_admin.py` | 219 | — | tenant admin: read tenant record | — | **A** | tenant là tham số; SQL nằm trong `_tenant_row` |
| `tenant_admin.py` | 236 | ĐỌC | tenant admin: list every tenant | tenant_members,tenants | **C** | liệt kê MỌI tenant |
| `tenant_admin.py` | 318 | GHI | tenant admin: create tenant | app,exc,tenants | **C** | tenant chưa tồn tại lúc chèn |
| `tenant_admin.py` | 415 | GHI | tenant admin: change the plan of a tenant | tenants | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_admin.py` | 455 | GHI | tenant admin: change the billing status of | tenants | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_admin.py` | 549 | GHI | tenant admin: record the owner of a self-s | tenants | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_admin.py` | 590 | GHI | tenant admin: update tenant record | tenants | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_admin.py` | 614 | GHI | tenant admin: soft-delete tenant | tenants | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_admin.py` | 632 | ĐỌC | tenant admin: list members of a tenant | tenant_members,users | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_admin.py` | 724 | GHI | tenant admin: add member to a tenant | memberships,users | **A!** | tra `users` theo id là bước DANH TÍNH — tách ra trước khi thu phạm vi, nếu không thêm thành viên từ tenant khác sẽ khớp 0 dòng |
| `tenant_admin.py` | 770 | GHI | tenant admin: change a member | tenant_members | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_admin.py` | 795 | GHI | tenant admin: remove a member from a tenan | a,tenant_members,the,users | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_admin.py` | 834 | GHI | tenant admin: move a user | memberships,users | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_admin.py` | 857 | ĐỌC | tenant admin: audit home tenant against me | tenant_members,users | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_admin.py` | 941 | GHI | tenant admin: invite a person into a tenan | tenant_invitations | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_admin.py` | 984 | ĐỌC | tenant admin: list invitations for a tenan | tenant_invitations | **A** | `where` có lọc tenant, tham số `(tenant_id,)` |
| `tenant_admin.py` | 996 | GHI | tenant admin: revoke an invitation | tenant_invitations | **A** | đang kiểm `row.tenant_id != tenant_id` BẰNG TAY — thu phạm vi làm chốt đó thành thừa |
| `tenant_admin.py` | 1041 | ĐỌC | tenant admin: resolve an invitation token | tenant_invitations | **B** | đối chiếu token trước khi biết tenant |
| `tenant_admin.py` | 1092 | GHI | tenant admin: accept an invitation | memberships,tenant_invitations,use | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_lifecycle.py` | 148 | GHI | lifecycle: record an export request | tenant_exports | **A** | INSERT mang cột tenant; WITH CHECK thoả |
| `tenant_lifecycle.py` | 168 | ĐỌC | lifecycle: read an export request | tenant_exports | **N** | TRA HẸP: khoá theo `export_id`, tenant chỉ biết SAU lượt đọc này |
| `tenant_lifecycle.py` | 175 | GHI | lifecycle: mark an export running | tenant_exports | **A** | sau 168 — tenant đã biết |
| `tenant_lifecycle.py` | 188 | ĐỌC | lifecycle: export rows of {table} | — | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_lifecycle.py` | 198 | ĐỌC | lifecycle: export the tenant record | tenants | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_lifecycle.py` | 216 | GHI | lifecycle: mark an export ready | tenant_exports | **A** | sau 168 — tenant đã biết |
| `tenant_lifecycle.py` | 229 | GHI | lifecycle: mark an export failed | tenant_exports | **A** | sau 168 — tenant đã biết |
| `tenant_lifecycle.py` | 286 | ĐỌC | lifecycle: list the exports of a tenant | tenant_exports | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_lifecycle.py` | 308 | ĐỌC | lifecycle: resolve an export file | tenant_exports | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_lifecycle.py` | 338 | ĐỌC | lifecycle: find expired exports | tenant_exports | **C** | quét bản ghi hết hạn của mọi tenant |
| `tenant_lifecycle.py` | 353 | GHI | lifecycle: mark an export expired | tenant_exports | **A** | theo từng dòng, `row.tenant_id` đã có |
| `tenant_lifecycle.py` | 385 | ĐỌC | lifecycle: preview a purge | tenant_exports,tenants,users | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_lifecycle.py` | 474 | GHI | lifecycle: purge every row of a tenant | tenant_members,users | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `tenant_lifecycle.py` | 526 | GHI | lifecycle: record the purge in the platfor | tenant_purges | **C** | sổ cái nền tảng; sau purge không còn tenant để thu phạm vi |
| `subscription_lifecycle.py` | 107 | ĐỌC | subscription: doc dang ky dang mo | tenant_subscriptions | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `subscription_lifecycle.py` | 173 | GHI | subscription: dat ky han | tenant_subscriptions | **A** | tenant là tham số |
| `subscription_lifecycle.py` | 197 | GHI | subscription: doi trang thai thanh toan | tenants | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `subscription_lifecycle.py` | 237 | ĐỌC | subscription: tim quan tri vien cua tenant | tenant_members,users | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `subscription_lifecycle.py` | 300 | ĐỌC | subscription: quet dang ky den han | tenant_subscriptions | **C** | quét mọi đăng ký đang mở |
| `subscription_lifecycle.py` | 328 | GHI | subscription: ghi moc nhac | tenant_subscriptions | **A** | theo từng dòng trong sweep |
| `subscription_lifecycle.py` | 347 | GHI | subscription: vao an han | tenant_subscriptions | **A** | theo từng dòng trong sweep |
| `subscription_lifecycle.py` | 382 | GHI | subscription: doi co tu gia han | tenant_subscriptions | **A** | tenant là tham số |
| `subscription_lifecycle.py` | 434 | GHI | subscription: mo dang ky moi | tenant_subscriptions | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `webhooks.py` | 156 | GHI | webhooks: register an endpoint for a tenan | webhook_endpoints | **A** | INSERT mang cột tenant |
| `webhooks.py` | 185 | ĐỌC | webhooks: list the endpoints of a tenant | webhook_endpoints | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `webhooks.py` | 202 | GHI | webhooks: delete an endpoint | webhook_endpoints | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `webhooks.py` | 268 | GHI | webhooks: queue a delivery for each listen | webhook_deliveries,webhook_endpoin | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `webhooks.py` | 357 | ĐỌC | webhooks: read the pending delivery queue | webhook_deliveries,webhook_endpoin | **N** | TRA HẸP: hàng đợi giao xuyên tenant theo bản chất |
| `webhooks.py` | 393 | — | webhooks: record a delivery outcome | — | **A** | sau 357 — dòng mang tenant |
| `webhooks.py` | 404 | — | webhooks: record a delivery error | — | **A** | sau 357 — dòng mang tenant |
| `webhooks.py` | 427 | GHI | webhooks: queue a test delivery | webhook_deliveries,webhook_endpoin | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `webhooks.py` | 464 | ĐỌC | webhooks: read recent deliveries of an end | webhook_deliveries | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `webhooks.py` | 481 | GHI | webhooks: purge old delivery history | webhook_deliveries | **C** | dọn theo `created_at`, mọi tenant |
| `api_keys.py` | 106 | GHI | api keys: create a key for a tenant | api_keys | **A** | INSERT mang cột tenant |
| `api_keys.py` | 140 | ĐỌC | api keys: list the keys of a tenant | api_keys | **A** | `where` lọc tenant |
| `api_keys.py` | 156 | GHI | api keys: revoke a key | api_keys | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `api_keys.py` | 198 | ĐỌC | api keys: authenticate a caller by key | api_keys,tenants | **N** | TRA HẸP: xác thực bằng khoá, tenant chưa biết |
| `api_keys.py` | 230 | GHI | api keys: stamp last_used_at | api_keys | **A** | sau 198 — `row.tenant_id` đã có |
| `plans.py` | 95 | ĐỌC | plans: read the platform price list | plans | **C** | bảng giá nền tảng |
| `plans.py` | 119 | ĐỌC | plans: read one plan | plans | **C** | bảng giá nền tảng |
| `plans.py` | 143 | ĐỌC | plans: resolve the plan of a tenant | tenants | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `plans.py` | 248 | GHI | plans: an operator edits the price list | exc,plans | **C** | người vận hành sửa bảng giá |
| `plans.py` | 276 | ĐỌC | plans: read the billing status of a tenant | tenants | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `plans.py` | 370 | — | plans: count {metric} of a tenant | — | **A** | mọi câu trong `USAGE_METRICS` đều `WHERE tenant_id = %s` |
| `usage.py` | 126 | ĐỌC | usage: list tenants for the storage sweep | tenants | **C** | liệt kê mọi tenant |
| `usage.py` | 178 | — | usage: roll up {metric} across tenants | — | **C** | gộp xuyên tenant |
| `usage.py` | 193 | — | usage: write the storage readings | — | **C** | ghi số đo cho mọi tenant trong một lô |
| `usage.py` | 247 | ĐỌC | usage: read the usage series of a tenant | tenant_usage_daily | **A** | máy: `tenant_id` ở mệnh đề lọc |
| `usage.py` | 291 | ĐỌC | usage: platform-wide usage table | tenant_usage_daily,tenants | **C** | JOIN chứ không phải lọc — dương tính giả của máy |

## Tổng

- **A → `tenant_scope`: 50**   (+ 1 chỗ A! cần tách bước danh tính)
- N tra hẹp bắt buộc: 3
- C xuyên tenant thật: 13
- B danh tính: 1

## Hình dạng lặp lại: *một lượt tra hẹp rồi thu phạm vi*

Năm cụm dưới đây trông như mười một chỗ xuyên tenant, nhưng thật ra mỗi cụm chỉ cần
**đúng một** lượt đọc xuyên tenant để tìm ra tenant chủ sở hữu; mọi thao tác sau đó
chạy được dưới `tenant_scope(row.tenant_id)`:

```
tenant_lifecycle  168 (export_id)      -> 175, 216, 229
tenant_lifecycle  338 (quét hết hạn)   -> 353
subscription      300 (quét đăng ký)   -> 328, 347
webhooks          357 (hàng đợi giao)  -> 393, 404
api_keys          198 (xác thực khoá)  -> 230
```

Đây là phần giảm bề mặt lớn nhất và rẻ nhất của cả đợt: **5 lượt đọc hẹp một bảng**
thay cho 11 khối `system_scope` mở toàn phần. Và nó cho một khuôn dùng lại được cho
mọi tác vụ nền tương lai — tác vụ nền khoá theo id thay thế thì tra tenant trước,
thu phạm vi ngay sau, chứ không chạy cả thân hàm trong phạm vi hệ thống.

## Hai chỗ đáng đọc kỹ

**`tenant_admin.py:996`** đang tự kiểm `row['tenant_id'] != tenant_id` bằng tay để
một quản trị viên không thu hồi được lời mời của tenant khác bằng cách đoán UUID.
Chuyển sang `tenant_scope` khiến chốt viết tay đó thành **thừa** — RLS làm đúng việc
ấy. Đây là ví dụ tốt nhất trong cả kho cho luận điểm *cưỡng chế ở tầng CSDL vá luôn
những hàm sẽ viết sau*, vì ở đây tác giả đã phải nhớ, và lần sau có thể quên.

**`tenant_admin.py:724`** là cái bẫy: khối này tra `users` theo `id` TRƯỚC khi chèn
membership. Thu phạm vi cả khối sẽ làm lượt tra đó khớp 0 dòng khi người được thêm
đang thuộc tenant khác — tức là thêm thành viên từ ngoài vào sẽ hỏng. Phải tách bước
tra danh tính ra ngoài phạm vi, rồi mới thu phạm vi cho phần ghi.
