# v4 — đợt hoàn thiện: nối dây, giao diện, và bốn lỗi tự tìm ra

**Ngày:** 2026-08-08 (đợt hai) · **Nhánh:** `deploy_ctu_ver-2.2.1` · **Chưa triển khai**

Tiếp theo [SAAS_V4_2026-08-08.md](SAAS_V4_2026-08-08.md), đợt đó dựng xong tám
hạng mục nhưng để lại năm việc dở. Tài liệu này ghi lại phần lấp chúng, và bốn
lỗi thật tìm ra trong lúc lấp.

---

## 1. Nối webhook vào đường ghi thật

Đợt trước khai báo sáu loại sự kiện và nối đúng **một**. Năm cái còn lại là
những cái tên nằm trong danh sách, hiện lên ô chọn ở giao diện, khách hàng đăng
ký nhận — và không dòng mã nào phát chúng.

| Sự kiện | Phát ở đâu | Ghi chú |
|---|---|---|
| `sample.created` | `upload.py` sau khi npz đã nằm trên đĩa | phát TRƯỚC là hứa một thứ còn có thể hỏng |
| `training.completed` | `training_tasks.py` sau khi ghi hợp đồng đầu ra | sự kiện giá trị nhất: lượt train chạy hàng chục phút |
| `training.failed` | trong `_escalate_system_failure` | xem dưới |
| `class.created` | `classes.py` sau khi đăng ký lớp | |
| `quota.exceeded` | `quota_deps.py` ở cổng chặn | sự kiện duy nhất phát từ đường THẤT BẠI |
| `tenant.plan_changed` | `billing.py` | đã có từ đợt trước |

**`training.failed` đặt trong phễu, không đặt ở ba chỗ gọi.** Cả ba đường dẫn
tới trạng thái `failed` (spawn hỏng, quá giờ, mã thoát khác 0) đều đi qua
`_escalate_system_failure`. Ba lời gọi là ba bản sao sẽ lệch ở lần thêm đường
hỏng thứ tư, và cái lệch đó im lặng. `cancelled` **không** đi qua đây, đúng:
người tự huỷ thì đã biết rồi.

**`quota.exceeded` có chống dội.** Một vòng lặp tải lên đang bị chặn gọi cổng ở
mỗi lượt; không hãm thì một buổi chiều hỏng sinh hàng nghìn lần giao. Khoá Redis
15 phút cho mỗi `(tenant, chỉ số)`. Redis chết thì vẫn phát, chỉ mất phần chống
dội — fail-open, cùng lý do với `rate_limit` và `trial`.

**Test canh khoảng trống này vĩnh viễn.**
`test_webhook_event_wiring.py` quét AST cây `app/` và đòi mỗi tên trong
`EVENT_TYPES` phải xuất hiện làm đối số ở một chỗ gọi.

Bản dò đầu tiên của tôi **sai**: nó tìm riêng những lời gọi tên `emit`, nên bỏ
sót hai sự kiện huấn luyện vì chúng đi qua hàm bọc `_emit_training_event`. Bộ
dò báo "chưa nối" cho mã đã nối đúng. Đổi sang khớp theo **giá trị** — tên sự
kiện xuất hiện làm đối số ở bất kỳ lời gọi nào — vừa đúng vừa không bắt người
viết phải đặt tên hàm bọc theo một quy ước không ai biết.

Giới hạn được nhận và ghi trong docstring: nó chứng minh tên được dùng như dữ
liệu ở một chỗ gọi, **không** chứng minh chỗ đó chạy tới `emit`.

---

## 2. Lỗi RLS làm chết cả hệ đo mức dùng

Chạy `app.cli.backfill_usage` lần đầu:

```
[USAGE] gộp samples_created cho 2026-07-30 hỏng:
        new row violates row-level security policy for table "tenant_usage_daily"
```

`_upsert` nằm **ngoài** khối `system_scope`:

```python
with system_scope(...):
    rows = _fetch_all(sql, ...)      # đọc: có scope
payload = [...]
written[metric] = _upsert(payload)   # ghi: KHÔNG có scope  ← RLS từ chối
```

Hệ quả nếu không phát hiện: tác vụ nền chạy mỗi giờ, ghi ra **số không**, mỗi
ngày, mãi mãi — chỉ để lại một dòng lỗi trong nhật ký của một tác vụ nền mà
không ai đọc. Trang "Mức dùng" hiện biểu đồ rỗng và trông như chưa có dữ liệu.

Đây là RLS làm **đúng** việc: ghi không scope thì hỏng theo hướng đóng. Chỗ sai
là ranh giới khối.

**Test cũ của tôi không bắt được, và đó là bài học riêng.**
`test_rolling_up_twice_gives_the_same_answer` so hai lượt gộp với nhau — hai
tập rỗng cũng bằng nhau. Đã thêm
`test_rollupDay_writesRowsRatherThanSilentlyWritingNothing`: tìm ngày có nhiều
mẫu nhất, gộp, và đòi số dòng ghi được **khác không** cùng tổng khớp `count(*)`
nguồn.

Sau khi vá, backfill 400 ngày cho ra dữ liệu thật: 23 ngày `samples_created`,
13 ngày `training_jobs_started`, 7 ngày `training_seconds`.

---

## 3. Giao diện

Hai trang mới, cùng API client và mục điều hướng.

**`/billing` mở cho MỌI thành viên**, không chỉ quản trị viên. Người bị chặn vì
hết hạn mức là người đang thao tác; nếu họ không xem được vì sao thì thông báo
"gói của bạn cho phép tối đa 500 mẫu" thành một điều bí ẩn họ không kiểm chứng
được.

**`/integrations` chỉ hiện cho quản trị viên** — backend đòi vai trò biên tập,
và mời người ta bấm vào một trang chắc chắn 403 là dẫn họ vào ngõ cụt. Cổng
thật vẫn ở backend; thanh điều hướng chỉ tránh mời nhầm.

**Ràng buộc thiết kế trung tâm: bí mật hiện đúng một lần.** Máy chủ chỉ lưu băm
khoá API và không endpoint nào đọc lại bí mật webhook. Nên hộp thoại hiện bí
mật **không đóng được cho tới khi người dùng bấm sao chép** — một dòng chữ nhỏ
"hãy lưu lại" là cách chắc chắn để người ta bỏ lỡ.

`navigator.clipboard` **không tồn tại** trong ngữ cảnh không bảo mật, đúng cấu
hình CTU hiện tại (http, không phải localhost). Nút sao chép xử lý được sự vắng
mặt đó và văn bản luôn `select-all` để còn đường thứ hai. Có test riêng cho
nhánh này.

**Kiểu dữ liệu là chỗ ép ràng buộc:** `ApiKeyCreated` có trường `key`, `ApiKey`
thì không; `WebhookCreated.secret` có, `Webhook.secret` không. Trình biên dịch
chặn mọi chỗ cố hiển thị bí mật từ danh sách, thay vì để chỗ đó hiện
`undefined`.

**Hai lỗi tự tìm ra khi viết phần này:**

- `await` bên trong hàm cập nhật truyền cho `setState`. Hàm đó phải thuần và
  đồng bộ — React gọi lại nhiều lần và không chờ Promise nào. `tsc` bắt được.
- Bọc `fireEvent.click` trong `act(async ...)` làm **cả bốn** test đụng tới nút
  treo tới hết timeout 5 giây. `fireEvent` đã tự bọc `act` cho lượt bấm, còn
  phần chờ Promise thì `findBy*`/`waitFor` lo; lồng thêm một `act` bất đồng bộ
  quanh chúng là chỗ treo.

Không thêm phụ thuộc nào: `@testing-library/user-event` chưa có trong dự án và
thêm một gói dev chỉ để bấm nút là cái giá không đáng.

---

## 4. Chú thích hứa một API không tồn tại

Migration v4.1 seed bảng giá bằng `ON CONFLICT DO NOTHING`, kèm chú thích:

> *"người vận hành sửa hạn mức bằng API quản trị, và một migration ghi đè lại
> mỗi lần khởi động sẽ âm thầm huỷ mọi chỉnh tay đó"*

API đó **không tồn tại**. Nghĩa là "chỉnh tay" chỉ có nghĩa là gõ SQL vào cơ sở
dữ liệu sản xuất.

Đã thêm `PATCH /billing/plans/{plan_code}` (đòi sudo, ghi kiểm toán kèm nội
dung thay đổi) và `plans.update_plan`. Ba quyết định đáng ghi:

- **Danh sách trắng cột sửa được**, không phải bảng tự do. `plan_code` vắng mặt
  có chủ ý: nó là khoá chính và có khoá ngoại từ `tenants` lẫn
  `tenant_subscriptions` trỏ tới.
- **Thân thư là đối tượng thưa**, không phải model Pydantic toàn `Optional`:
  với model đó không phân biệt được "không nêu" và "đặt về null", mà null ở đây
  nghĩa là KHÔNG GIỚI HẠN — gần như trái ngược với "để nguyên".
- **Xoá bộ đệm ngay sau khi ghi.** `get_plan` đệm 30 giây; không xoá thì người
  vận hành vừa sửa xong tải lại trang và thấy số cũ, rồi sửa lần nữa.

---

## 5. Hai rò rỉ teardown do chính v4 gây ra

Sổ dấu vết bắt được cả hai. Cùng một nguyên nhân: từ v4, **một lượt đăng ký
không còn chỉ chèn một hàng `users`** — nó tạo hẳn một tenant kèm bản sao danh
mục từ vựng.

Sổ bắt được chúng ở **ba lượt chạy liên tiếp**, mỗi lượt một fixture khác:

| Lượt | Fixture | Để lại |
|---|---|---|
| 1 | `TestRegistration._cleanup` | 29 tenant mồ côi |
| 2 | `test_login_rate_limit._drop` | 27 tenant + 243 hàng `dialects` |
| 3 | `test_legal_consent._purge` | 5 tenant |

Điểm chung: teardown viết cho hình dạng cũ của một thao tác, và hình dạng đó
đổi ở tầng dưới. Không có sổ dấu vết thì chúng tích lại qua từng lượt chạy.

**Vá lần thứ ba mới là vá đúng chỗ.** Hai lần đầu tôi sửa từng fixture — đúng
cái cách đã hỏng bốn lần trước đó với các rò rỉ khác. Đến lần thứ ba thì rõ:
có **bốn** bản gần giống nhau của cùng một việc dọn nằm ở bốn tệp, và ba trong
bốn bản viết cho thời "một lượt đăng ký chèn đúng một hàng `users`".

Đã gom về `conftest.purge_registered_account(username)`, một bản, cả bốn tệp
gọi vào. Nó tự tra id, tự tìm tenant mà lượt đăng ký tạo ra, và **chỉ xoá
tenant có cờ `is_self_serve`** — tenant do lời mời cấp thuộc về fixture khác.
Lần sau hình dạng của "đăng ký" đổi thì chỉ có một chỗ phải sửa.

**Ghi chú vận hành:** sổ xoá mọi hàng xuất hiện trong lúc suite chạy. Chạy
`backfill_usage` **song song** với suite thì 101 hàng số đo bị coi là dấu vết
test và bị xoá. Thứ tự đúng: chạy suite xong rồi mới backfill.

---

## 6. Kết quả

| | Trước đợt này | Sau |
|---|---|---|
| Sự kiện webhook được nối | 1/6 | **6/6**, có test canh |
| Bảng `tenant_usage_daily` | ghi được 0 hàng (lỗi RLS) | dữ liệu thật 400 ngày |
| Trang giao diện cho v4 | 0 | 2 (`/billing`, `/integrations`) |
| Sửa bảng giá | chỉ bằng SQL tay | API có sudo + kiểm toán |
| Test frontend | 170 | **183** (27 tệp) |
| Test backend mới đợt này | — | 16 (event wiring 7, plan admin 9) |

`tsc --noEmit` sạch, `npm run build` sạch.

---

## 7. Phát hiện khi mở rộng verifier: production KHÔNG thu chấp thuận nào

Đã thêm bốn phép kiểm v4 vào `app.cli.verify_deployment` (bảng giá có seed
không, tenant nào chưa có gói, tenant nào chưa có đăng ký đang mở, số đo đã lấp
chưa). Chạy thử trên bản sao thì một phép kiểm **có sẵn từ trước** bật đỏ:

```
FAIL  van ban phap ly   chua cong bo: terms, privacy
                        - dang ky KHONG thu chap thuan
```

Kiểm lại trên `signdb` thật: `SELECT count(*) FROM legal_documents` → **0**.

Toàn bộ bộ máy chấp thuận đã tồn tại và hoạt động đúng — bảng `user_consents`,
`content_hash` chống sửa nội dung dưới chân chữ ký, ghim theo số hiệu bản, băm
địa chỉ IP làm bằng chứng. Nhưng **công bố văn bản CHÍNH LÀ bật cưỡng chế**
(xem `routers/auth.py:_validate_consents`), nên chưa công bố nghĩa là mọi tài
khoản từ trước tới nay được tạo mà không đồng ý gì cả, và không có gì trong hệ
thống báo điều đó ngoài phép kiểm này.

Đây là tình trạng **có từ trước v4**, không phải do đợt này gây ra. Nhưng với
một nền tảng thu dữ liệu của người khuyết tật kèm phiếu chấp thuận của người
ký, nó đáng đứng riêng một mục.

**Không tự xử được, và không nên tự xử.** Nội dung điều khoản và chính sách
quyền riêng tư là văn bản pháp lý của tổ chức — tôi bịa ra một bản rồi công bố
thì thứ thu được còn tệ hơn không thu gì: một chữ ký trỏ vào văn bản không ai
có thẩm quyền viết. Việc cần làm:

```
docker exec voya_backend python -m app.cli.register_legal_document \
    --kind terms   --version <ngày> --file <đường dẫn văn bản thật>
docker exec voya_backend python -m app.cli.register_legal_document \
    --kind privacy --version <ngày> --file <đường dẫn văn bản thật>
```

Lưu ý thứ tự khi làm: công bố xong là **mọi lượt đăng ký mới bị chặn** cho tới
khi giao diện gửi kèm số hiệu bản.

> **Sửa lại: câu tiếp theo ở bản đầu viết sai.** Tôi đã viết "giao diện đã gửi
> (`RegisterPage` đọc `/legal/{kind}`)". Không đúng — lúc đó `RegisterPage`
> không hề chạm tới `/legal`, và toàn bộ frontend không có một tham chiếu nào
> tới `legal`. Công bố văn bản khi ấy sẽ làm hỏng đăng ký trên toàn hệ thống.
> Việc này đã được làm ở đợt v5; xem `LEGAL_V5_2026-08-08.md`.

---

## 8. CÒN LẠI

1. **Triển khai.** `signdb` thật vẫn chưa có bảng v4. Trình tự: sao lưu → build
   ảnh backend → force-recreate → `schema_debt()` sạch → 3 lượt boot không cảnh
   báo → `backfill_usage --days 400`.
2. **Chưa commit gì.**
3. ~~Rate limit chưa theo khoá API.~~ **Tôi ghi sai mục này ở bản đầu.**
   `enforce_actor_limit` vốn đã khoá theo `user_id` khi biết người gọi, và
   `_user_from_api_key` trả về `id = "apikey:<uuid>"`, nên mỗi khoá đã có thùng
   đếm riêng — không chia với người dùng trình duyệt cùng NAT. Đã thêm
   `test_apiKeyCaller_getsItsOwnBucketNotTheSharedIpBucket` để tính chất đó
   không lặng lẽ hỏng nếu ai đó bỏ trường `id` cho gọn.
4. **Kiểm SSRF của webhook là kiểm TÊN MÁY**, không phải IP đã phân giải. Một
   tên miền công khai trỏ về 127.0.0.1 vẫn lọt. Đã ghi trong docstring
   `_validate_url`.
5. **Công bằng hàng đợi train là hạn ngạch, không phải lịch biểu.** Nó giới hạn
   mỗi tenant chiếm bao nhiêu hàng đợi, không xen kẽ lượt. Lập lịch chia lượt
   thật cần bộ chạy tự chọn job thay vì nhận từ Celery.
6. **Đăng ký giờ nặng hơn**: mỗi lượt tự phục vụ sao chép cả danh mục từ vựng
   (~9 dialect + hồ sơ). Bắt buộc vì khoá ngoại ghép, nhưng một đợt đăng ký ồ
   ạt sẽ thấy được. Chưa cần xử lý ở quy mô này; ghi lại để không ngạc nhiên.
