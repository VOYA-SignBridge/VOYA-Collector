# Vòng đời đăng ký

*Dựng 2026-08-10. Mã: `backend/app/subscription_lifecycle.py`,
`backend/app/saas_tasks.py::sweep_subscriptions`. Test:
`backend/tests/test_subscription_lifecycle.py` (17).*

---

## 1. Điều phải đọc trước mọi thứ khác

**Hệ thống này không thu tiền.** Không có cổng thanh toán, không có hoá đơn,
không có bút toán. `auto_renew = TRUE` nghĩa là *"tới hạn thì mở kỳ tiếp theo"*,
**không** phải *"trừ tiền thẻ"*. Việc thu tiền diễn ra ngoài hệ thống — bằng hợp
đồng, chuyển khoản, hay bất cứ cách nào tổ chức thoả thuận — và bảng
`tenant_subscriptions` chỉ ghi lại **quyết định** đó.

Đây là chỗ dễ hiểu nhầm nhất của cả cơ chế, nên nó được viết ra ở bốn nơi: đầu
tệp `subscription_lifecycle.py`, docstring của `sweep()`, docstring của tác vụ
Celery, và ở đây. Ai đọc tên `auto_renew` rồi kết luận có một giao dịch nào đó
đang chạy sẽ sai.

## 2. Khoảng trống được lấp

Trước 2026-08-10, `tenant_subscriptions` có `started_at` và `ended_at` (thời
điểm bị đóng) — và **không cột nào nói bao giờ hết hạn**. Hệ quả dây chuyền:

| Không có | Nên không có |
|---|---|
| mốc kết thúc | hết hạn |
| hết hạn | gia hạn |
| gia hạn | thứ để nhắc |
| ranh giới quá hạn | ân hạn để đệm |

Và `plans.trial_days` chưa từng được một dòng mã nào đọc tới — cột trang trí
theo đúng nghĩa đen. Lịch Celery beat có 5 tác vụ định kỳ, không tác vụ nào
chạm tới đăng ký.

## 3. Bốn trạng thái, và chúng KHÔNG phải cơ chế mới

Trạng thái sống ở `tenants.billing_status`, đã có từ v4 cùng ràng buộc
`ck_tenants_billing_status`. `plans.assert_writable()` đã cưỡng chế nó ở mọi
đường ghi. Module này chỉ **di chuyển** trạng thái theo thời gian — nó không
dựng thêm một lớp khoá thứ hai.

> Một cơ chế thứ hai chạy song song là cách chắc chắn để hai cái bất đồng, và
> lúc đó không ai biết cái nào đang có hiệu lực.

| Trạng thái | Ghi được? | Nghĩa |
|---|---|---|
| `trialing` | có | đang trong thời gian dùng thử |
| `active` | có | bình thường |
| `past_due` | **có** | đã quá hạn, đang trong ân hạn |
| `suspended` | **không** | chỉ đọc — "khoá mềm" |
| `cancelled` | không | người dùng đã dừng hẳn |

**`past_due` vẫn ghi được là chủ ý**, và quyết định đó có từ trước module này:
khoá dữ liệu của một trường vì hoá đơn trễ hai ngày là cách nhanh nhất để mất
họ, và số tiền không vì thế mà đòi được nhanh hơn.

## 4. Khoá mềm không bao giờ xoá gì

Hết hạn là một **sự kiện thương mại**, không phải một phán quyết về dữ liệu.

- Dữ liệu còn nguyên vẹn.
- Đường xuất dữ liệu (`POST /tenants/{id}/exports`) **vẫn chạy** khi tenant
  `suspended`. Đó là chủ ý: người dùng phải luôn lấy lại được thứ họ đã đóng góp.
- Giao diện và thư nhắc đều phải nói ra điều này. Một cảnh báo chỉ liệt kê cái
  mất làm người đọc tưởng dữ liệu đã bay — và lần sau họ sẽ không tin thư nào
  nữa. Có test ghim câu chữ này ở cả hai phía
  (`OrganizationPage.test.tsx::chỉ-đọc nói rõ dữ liệu VẪN CÒN`).

## 5. Lượt quét

`app.saas_tasks.sweep_subscriptions` → `subscription_lifecycle.sweep()`, chạy
**mỗi giờ**.

Vì sao mỗi giờ chứ không mỗi ngày: một tác vụ 24 giờ một lần mà trúng lúc worker
khởi động lại thì lỡ nguyên một ngày — và "lỡ một ngày" ở đây nghĩa là một tổ
chức đã hết ân hạn vẫn ghi thêm 24 giờ, hoặc thư "còn 1 ngày" tới sau khi đã hết
hạn. Lượt quét idempotent nên chạy thừa không tốn gì.

Thứ tự xét cho **mỗi** đăng ký, và thứ tự này quan trọng:

```
chưa tới hạn         → tới mốc nhắc nào chưa (7 / 3 / 1 ngày)
tới hạn + auto_renew → mở kỳ mới, trạng thái về `active`
tới hạn, không tự gia hạn, chưa có grace_until
                     → vào ân hạn: grace_until = end + SUBSCRIPTION_GRACE_DAYS,
                       billing_status → `past_due`  (VẪN GHI ĐƯỢC)
đã qua grace_until   → billing_status → `suspended`  (CHỈ ĐỌC)
```

Mỗi đăng ký nằm trong `try` riêng: **một tenant hỏng không được làm hỏng lượt
quét.** Đây là bài học đã trả giá ở teardown của bộ test — một câu ném ngoại lệ
giữa chừng thì mọi thứ xếp sau nó không bao giờ chạy tới.

## 6. Chống gửi trùng, và vì sao nó không tầm thường

Cột `last_reminder_days` giữ mốc **gần nhất đã gửi**. Tác vụ chạy mỗi giờ, nên
thiếu cột này thì một người nhận **24 lá thư "còn 7 ngày" trong một ngày** — đủ
để họ lọc mọi thư của hệ thống vào thùng rác.

Bẫy thứ hai, đã mắc và đã sửa trong chính đợt này: `_reminder_due` phải lấy mốc
**gần nhất còn áp dụng**, không phải mốc khớp đầu tiên. `REMINDER_DAYS` giảm dần
`(7, 3, 1)`, nên thoát sớm ở mốc đầu tiên khớp sẽ luôn chốt vào `7`; khi còn 0
ngày thì phép so `7 < 7` cho ra "đã gửi rồi", và người dùng nhận đúng **một** lá
thư ở mốc 7 ngày rồi không nghe gì nữa cho tới lúc mất quyền ghi.
`test_moc_gan_hon_thi_gui_tiep` canh đúng chỗ đó.

Mốc được ghi **kể cả khi gửi được 0 thư**. Nếu không, một hộp thư hỏng làm lượt
quét thử lại mỗi giờ cho tới hết kỳ.

## 7. Kỳ đầu tiên của gói có dùng thử

Gói `school` có `trial_days = 14` và `billing_period = monthly`. Kỳ **đầu** dài
14 ngày, không phải 30 — và cũng **không phải 44**. Cộng dồn hai khoảng là tặng
không nửa tháng cho mỗi khách hàng mới, và người đọc hoá đơn sẽ thấy.

Gói không có kỳ hạn (`billing_period = 'none'`) thì các cột kỳ hạn để **NULL**,
không phải một ngày rất xa. `NULL` đọc được là "không áp dụng"; một ngày năm
2999 trông như dữ liệu hỏng. Giao diện nhận `days_left = null` và vẽ "Gói không
có kỳ hạn" — vẽ "còn 0 ngày" cho một gói vĩnh viễn là câu sai đủ để người dùng
gọi điện.

## 8. Tự huỷ

`POST /tenants/{id}/subscription/auto-renew` với `{"enabled": false}`.

**Tắt tự gia hạn KHÔNG đóng đăng ký ngay.** Kỳ đang chạy vẫn chạy hết. Đây là
chỗ dễ làm sai nhất của mọi luồng huỷ, và làm sai theo hướng đó là lấy đi phần
khách hàng đã trả tiền. Hộp thoại xác nhận ở giao diện nói thẳng câu này, và có
test ghim nó.

## 9. Cấu hình

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `SUBSCRIPTION_GRACE_DAYS` | `7` | ân hạn sau khi kỳ kết thúc. `0` là bỏ hẳn ân hạn — hợp lệ, nhưng khi đó một hoá đơn trễ một ngày khoá quyền ghi của cả một trường |
| `SUBSCRIPTION_SWEEP_ENABLED` | `1` | đặt `0` để tắt hẳn lượt quét, không phải sửa lịch beat rồi dựng lại ảnh |

## 10. Chín bước — cái có và cái không

Bản kiểm 09/08 đo được **0/9**. Nay:

| Bước | Trạng thái |
|---|---|
| Kỳ hạn (`period_start` / `period_end`) | **có** |
| Tự gia hạn (cờ + tác vụ định kỳ) | **có** |
| Nhắc trước hạn (7 / 3 / 1 ngày) | **có** |
| Ân hạn | **có** |
| Khoá mềm (chỉ đọc, không mất dữ liệu) | **có** |
| Hạ gói tự động khi hết hạn | **có** — qua `suspended`, không đổi `plan_code` |
| Rời nền tảng (xuất toàn bộ rồi đóng) | **có** (đã có từ trước) |
| Xử lý thanh toán hỏng / nhắc nợ | **không** — cần cổng thanh toán |
| Hoá đơn / biên nhận / VAT | **không** — cần cổng thanh toán và một pháp nhân |

Hai dòng cuối **không được viết là "sắp có"**. Chúng cần một cổng thanh toán và
một pháp nhân xuất hoá đơn; cả hai đều nằm ngoài phần mềm.

## 11. Vận hành

Chạy tay một lượt quét (không cần Celery):

```bash
docker compose exec backend python -c \
  "from app.subscription_lifecycle import sweep; print(sweep())"
```

Xem một tổ chức:

```bash
docker compose exec backend python -c \
  "from app.subscription_lifecycle import describe; print(describe('default'))"
```

Toàn bộ luật nằm trong module chứ không trong tác vụ Celery, đúng để hai lệnh
trên chạy được — **một quy tắc nghiệp vụ chỉ chạy được bên trong một tác vụ nền
là quy tắc không ai kiểm được.**
