# Dấu vết kiểm toán — ghi gì, không ghi gì, và vì sao

*Soát lại 11/08/2026.*

## 1. Hai nhật ký, hai câu hỏi

Đừng nhầm chúng, vì trông chúng giống nhau trên màn hình.

| | `sec:log` (Redis) | `audit_log` (Postgres) |
|---|---|---|
| Trả lời | *"vừa có chuyện gì?"* | *"ai đã làm gì, tháng trước?"* |
| Tuổi thọ | 500 mục, `volatile-lru` — **mất được** | không bị đuổi |
| Phạm vi | toàn cục | có RLS theo tenant |
| Nơi hiện | bảng "Nhật ký bảo mật" | bảng "Nhật ký kiểm toán" |

Cả hai được ghi từ **một** lối gọi (`activity.log_security_event`), bản bền ghi
**trước**. Cửa sổ giữa hai lượt ghi chỉ vài mili giây, nhưng nếu tiến trình chết
đúng lúc đó thì thứ tự quyết định cái nào sống sót — và cái đáng giữ là cái
không bị đuổi khỏi bộ nhớ.

## 2. Tiêu chí: cái gì đáng ghi

Một câu hỏi duy nhất:

> *Nếu việc này xảy ra mà không ai nhớ, sáu tháng sau có ai cần biết ai đã làm
> không?*

Đổi vai một thành viên thì **có**. Đánh dấu một thông báo là đã đọc thì
**không**. Ghi mọi thứ nghe có vẻ an toàn hơn, nhưng một bảng đầy sự kiện vô
thưởng vô phạt là một bảng không ai đọc, và lúc đó nó bảo vệ được đúng bằng
không.

## 3. Đang ghi

### Mặt phẳng an ninh — `security.*`

Bảy lối vào đi qua `activity.log_security_event`: `block_ip`, `unblock_ip`,
`force_logout`, `lock_user`, `unlock_user`, `warn_user`, và các sự kiện hệ
thống. Thêm từ đợt này:

| Hành động | Vì sao |
|---|---|
| `security.2fa.disabled` | tắt yếu tố thứ hai là **đúng việc** người chiếm được mật khẩu sẽ làm đầu tiên. Nó có đòi mật khẩu nên không phải lỗ hổng — nhưng khi chủ tài khoản quay lại hỏi "chuyện gì đã xảy ra", thứ trả lời được là một dòng có mốc thời gian và địa chỉ, không phải cột `enabled = false` vốn chỉ nói trạng thái **hiện tại**. |
| `security.2fa.recovery_codes_regenerated` | cấp lại giết bộ mã cũ. Nếu chủ tài khoản không phải người bấm, lần sau họ dùng mã cũ sẽ bị từ chối mà không hiểu vì sao. |
| `security.sot.machine_registered` | cấp cho một máy quyền **ký SOT**, tức quyền công bố danh mục mà cả hệ thống tin. Bảng `sot_authorized_keys` nói máy nào *đang* được phép; nó không nói ai đã cho phép. |
| `security.sot.machine_revoked` | thu hồi làm một máy đang chạy mất quyền giữa chừng. Triệu chứng ở đầu kia là `sot-init` thoát mã 4 và **cả stack không lên** — một sự cố trông như lỗi hạ tầng. |

### Dữ liệu của người khác bị di chuyển — `data.*`, `vocabulary.*`

| Hành động | Vì sao |
|---|---|
| `data.class.purge`, `data.sample.purge` (+ `.bulk`) | xoá vĩnh viễn, không hồi được |
| `vocabulary.dialect.merged` | **gộp phương ngữ đổi nhãn mọi mẫu người đóng góp đã thu** dưới phương ngữ đó, và không có nút hoàn tác. `vr.record_merge` giữ được sự kiện trong registry, nhưng registry trả lời "phương ngữ này đi đâu" — không trả lời "ai quyết định thế, lúc nào, từ máy nào", mà đó mới là câu hỏi khi có người khiếu nại rằng dữ liệu của họ bị đổi nhãn. |
| `vocabulary.dialect.approved` | biến một đề xuất thành mục chính thức; mọi mẫu thu sau đó dựa vào quyết định ấy |

### Quyền trong tổ chức — `tenant.*`

| Hành động | Vì sao |
|---|---|
| `tenant.member_role_changed` | đổi vai là **đổi quyền**. `detail` chở cả `role_cu` lẫn `role_moi`, vì "nâng từ viewer lên admin" và "hạ từ admin xuống viewer" là hai câu chuyện khác nhau mà một dòng chỉ có vai mới không phân biệt được. |
| `tenant.member_removed` | người bị gỡ mất quyền xem chính dữ liệu họ đã đóng góp; sau khi hàng `tenant_members` biến mất thì không còn gì nói rằng họ đã từng ở đây |
| `tenant.plan_changed`, `tenant.status_changed`, `tenant.purged` | (đã có từ trước) |

### Còn lại

`legal.publish`, `legal.upload`, `sudo.elevate` / `.failed` / `.revoke`,
`settings.update`, `account.username.change`, `plan.updated`,
`webhook.created` / `.deleted`.

## 4. CỐ Ý không ghi

- **Đọc.** Xem một phiếu hỗ trợ, mở một trang. Ghi mọi lượt đọc là biến bảng
  kiểm toán thành nhật ký truy cập, và nhật ký truy cập đã có ở tầng nginx.
- **Thao tác của chính chủ tài khoản trên dữ liệu của mình** — thu mẫu, đổi
  ảnh đại diện. Chúng đã có dấu vết riêng trong chính dữ liệu đó.
- **Đánh dấu thông báo đã đọc**, đóng/mở phiếu hỗ trợ. Hồi được, không mất mát.
- **Lượt đăng nhập thành công.** Đã có ở `sec:log` và ở `refresh_tokens`; nhân
  đôi vào bảng bền chỉ làm nó dài thêm mà không thêm thông tin.

## 4b. Dùng `log_security_event`, không gọi thẳng `audit.record`, cho `security.*`

`activity.log_security_event("2fa.disabled", …)` ghi vào **cả hai** nhật ký và
tự thêm tiền tố `security.`. Gọi thẳng `audit.record("security.2fa.disabled")`
cũng chạy — nhưng sự kiện khi ấy mang tiền tố an ninh mà lại **vắng mặt ở bảng
"Nhật ký bảo mật"**, tức bảng mà người ta mở ra để xem "vừa có chuyện gì". Một
chỗ lệch như thế không báo lỗi và người đọc không có cách nào đoán ra.

Hai tham số tên gần giống nhau và không thay thế nhau được:

- `actor` — **chuỗi tên**, cho nhánh Redis hiển thị;
- `actor_user` — **dict người dùng đầy đủ**, để `audit.record` điền được khoá
  ngoại `actor_user_id`.

Thiếu `actor_user` thì dòng bền mất danh tính người thực hiện, và một dòng kiểm
toán không biết ai làm thì gần như vô dụng.

## 5. Hai luật khi viết một dòng mới

**Khuôn tên là `mien.doi_tuong.viec`.** `AdminActivityPage` lọc theo **tiền
tố**. Một hành động đặt ngoài khuôn vẫn ghi được, vẫn đọc được bằng SQL, vẫn
hiện dưới "Tất cả" — nhưng **không lọc ra được**, và ở một bảng chỉ dài thêm
theo thời gian thì "không lọc ra được" và "không tìm thấy" là cùng một thứ với
người đang cần nó. Mỗi tiền tố máy chủ ghi ra phải có một nút trong
`AUDIT_FILTERS`.

**`detail` không mang bí mật.** `audit._redact` che theo **tên khoá**, nên nó
chỉ cứu được khi người viết đặt tên trùng danh sách; `detail={"codes": [...]}`
lọt qua sạch sẽ. Rẻ hơn là đừng đưa vào ngay từ đầu.

## 6. Phạm vi — chỗ dễ hiểu nhầm nhất

`audit.record` **fail-closed khi không có phạm vi nào**. Trong system scope,
dòng nằm ở tầng nền tảng (`tenant_id` NULL) và chỉ đọc lại được trong system
scope. Trong tenant scope, dòng mang tenant đó. Nhưng **ngoài mọi phạm vi** thì
vị từ RLS cho ra NULL chứ không phải TRUE, `WITH CHECK` từ chối, và vì hàm nuốt
lỗi nên dấu vết biến mất lặng lẽ — chỉ còn một dòng `[AUDIT-FAIL]` trong log.

Sản xuất không rơi vào đó: middleware HTTP, `task_prerun` của Celery, và
`platform_command` của CLI đều đặt phạm vi. **Một lối vào thứ tư thì phải tự
đặt lấy.**

## 7. Kiểm chứng

```bash
pytest tests/test_audit_log.py -q        # ghi/đọc, che bí mật, fail-closed, chỉ số
pytest tests/test_audit_coverage.py -q   # 14 test — danh sách hành động PHẢI có dấu vết
```

`test_audit_coverage.py` giữ một **danh sách tường minh**. Lý do: một hành động
thiếu dấu vết **không hỏng gì cả** — endpoint chạy đúng, người dùng thấy đúng
kết quả, không có lỗi nào ở đâu. Nó chỉ hỏng vào tháng sau, khi ai đó hỏi "ai
gộp phương ngữ này?" và câu trả lời là không có câu trả lời. Không một bộ test
hành vi nào bắt được loại thiếu sót đó, vì không có hành vi nào sai.

## 8. Còn thiếu (biết, chưa làm)

- `experiments.py` (8 phép ghi) và `training.py` (5) chưa có dòng nào. Chúng
  tạo/xoá lượt chạy huấn luyện — hồi được, và đã có `training_jobs` làm dấu vết
  riêng, nên xếp dưới nhóm trên. Đáng thêm khi có tranh chấp về một kết quả.
- `tenants.delete_tenant` chưa ghi (`tenant.purged` chỉ phủ đường purge).
- Chưa có cách xuất một dải nhật ký ra tệp cho kiểm toán ngoài; hiện phải truy
  vấn thẳng cơ sở dữ liệu.
