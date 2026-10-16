# Thông báo và kênh hỗ trợ

*Xây 2026-08-10. Mã: `app/notifications.py`, `app/support.py`,
`app/routers/{notifications,support}.py`, `frontend/src/pages/{NotificationsPage,SupportPage}.tsx`,
`frontend/src/components/NotificationBell.tsx`.*

---

## 1. Vì sao cần, khi đã có thư điện tử

Thư rời khỏi hệ thống rồi không quay lại: không ai biết người dùng đã đọc chưa,
thư vào hộp rác thì mất hẳn, và một người đổi địa chỉ thư là mất luôn lịch sử.
Bảng `notifications` là bản ghi **bền** của cùng những sự kiện đó.

Thư vẫn giữ nguyên — hai kênh bổ sung nhau, không thay thế nhau.

## 2. Nguyên tắc: loại nào cũng phải có lý do người dùng quan tâm

Đây **không phải** nhật ký hệ thống chuyển hướng vào giao diện — nhật ký đã có
`audit_log` và Loki. Mỗi mục ở `notifications.KINDS` tương ứng một việc mà người
dùng cần biết để **hành động** hoặc để **yên tâm**:

| Loại | Người dùng làm gì với nó |
|---|---|
| `subscription` | gia hạn trước khi bị khoá mềm |
| `consent` | ký lại văn bản pháp lý mới |
| `security` | nhận ra một lần đăng nhập không phải của mình |
| `training` | biết phiên huấn luyện đã xong |
| `support` | thấy người trực đã trả lời |
| `data` | tải bản xuất khi nó sẵn sàng |
| `system` | biết trước lịch bảo trì |

Thêm loại mà không trả lời được "người ta làm gì với thông tin này" là cách biến
cái chuông thành thứ ai cũng tắt.

## 3. Hai hướng hỏng, hai chiều khác nhau

**`notify()` không bao giờ ném.** Thông báo là việc *phụ* của một thao tác đã
thành công: một phiên huấn luyện chạy xong rồi thì không được phép báo lỗi chỉ vì
cái chuông ghi hụt. Hỏng thì ghi `ERROR` và đi tiếp.

**Nhưng thiếu phạm vi tenant thì KHÔNG ghi.** Fail-closed, cùng nguyên tắc với
`audit.record()`: một dòng không biết mình thuộc tenant nào là một dòng mà RLS sẽ
giấu khỏi chính người cần đọc nó — tệ hơn hẳn việc không ghi.

## 4. Ranh giới quyền

`user_id` trong mệnh đề `WHERE` của `mark_read` **không phải chỗ dư thừa**.
Thiếu nó, bất kỳ ai đoán được một UUID sẽ đánh dấu đã đọc hộ người khác — nghe
vô hại, nhưng nó có nghĩa là **một thông báo bảo mật có thể bị người ngoài làm
cho biến mất khỏi tầm mắt nạn nhân**. Ghim ở `test_KHONG_danh_dau_ho_nguoi_khac`.

Với phiếu hỗ trợ: "không tìm thấy" và "không có quyền" trả về **cùng một lỗi
404**. Phân biệt hai cái cho phép dò xem một mã phiếu có tồn tại hay không.

## 5. Ba chi tiết nhỏ có lý do

**Chuông chỉ hỏi số, không hỏi danh sách.** `GET /notifications/unread-count` trả
một số nguyên. Gọi `GET /notifications` theo chu kỳ để hiển thị một chữ số là tải
về vài chục kilobyte mỗi lượt cho không. Chu kỳ 60 giây, **dừng khi tab bị ẩn**:
một tab để quên qua đêm sẽ gọi 480 lượt vô ích.

**Nhãn của chuông mang cả con số** (`"Thông báo, 3 chưa đọc"`). Chấm tròn đỏ
không được trình đọc màn hình đọc ra, nên nhãn là chỗ **duy nhất** người khiếm
thị biết có gì mới. WCAG 1.4.1 — xem `docs/05-frontend/ACCESSIBILITY.md`.

**Mở một thông báo thì đánh dấu đã đọc NGAY**, không chờ một nút riêng. Nút "đánh
dấu đã đọc" tách rời là thứ không ai bấm, và hệ quả là số trên chuông không bao
giờ về 0 — rồi người dùng học cách bỏ qua nó hoàn toàn.

## 6. Phiếu hỗ trợ: trạng thái đi theo AI vừa nói

Người trực trả lời → `pending` (chờ người dùng). Người dùng trả lời → `open` (mở
lại, kể cả khi phiếu đã `resolved`).

Một nút "đổi trạng thái" tách rời là nút không ai bấm, và hàng đợi của người trực
sẽ đầy những phiếu đã xong từ lâu.

Người dùng **chỉ được đóng** phiếu của mình; đánh dấu `resolved` là việc của
người trực. Người dùng tự đánh dấu đã giải quyết thì con số "thời gian xử lý
trung bình" mất hết ý nghĩa.

## 7. `author_label` là bằng chứng lịch sử

Tên tác giả được **chép cứng** lúc ghi và **không** đổi theo lượt đổi tên tài
khoản — cùng nguyên tắc với `audit_log.actor_label`. Nếu nhãn chạy theo tên hiện
tại, đọc lại một phiếu cũ sẽ thấy những cái tên chưa từng tồn tại vào lúc đó.

Test ghim điều này bằng **cấu trúc**, không bằng cách gọi `rename_user` thật:

> Hàm đó ghi lại `dataset/samples.csv` — tệp **sản xuất**, không phải bản sao —
> nên gọi nó trong một test là sửa dữ liệu thật của người dùng. Bản đầu của test
> này có gọi, và nó **treo bộ test 8 phút** vì phải viết lại 3.860 dòng.

Cách thay thế còn chứng minh mạnh hơn: nó ghim rằng `support_messages` **không có
tên** trong `app/account_rename.py`, tức là không có đường nào để lượt đổi tên
chạm tới nó.

## 8. Chưa có

- **Không có đường tự động sinh thông báo từ các sự kiện đang có.** Chỉ
  `support.reply` gọi `notify()`. Nối vòng đời đăng ký, huấn luyện và đồng thuận
  vào đây là việc tiếp theo, và nó rẻ — mỗi chỗ một dòng.
- **Không có tuỳ chọn tắt từng loại.** Khi số lượng còn nhỏ thì một danh sách
  tuỳ chọn chỉ là màn hình thừa; thêm khi có người phàn nàn, không phải trước.
- **Không có đẩy thông báo (push).** Cần service worker + khoá VAPID.
- **Phiếu hỗ trợ chưa có đính kèm tệp.** Người dùng dán mô tả bằng chữ.

## 9. Kiểm chứng

```bash
pytest tests/test_notifications_support_2fa.py -q     # 45 test
pytest tests/test_support_bot.py -q                   # 19 test (trợ lý tự động)
pytest tests/test_support_backlog.py -q               # 13 test (tồn đọng + thư)
npx vitest run src/pages/__tests__/NotificationsPage.test.tsx   # 11 test
npx vitest run src/hooks/__tests__/useAdminAttention.test.tsx   # 6 test (huy hiệu + pop-up)
```

---

# Phần II — Thư cho người trực, tồn đọng, và huy hiệu console

*(bổ sung 11/08/2026)*

## 10. Vì sao chuông trong ứng dụng là chưa đủ

Chuông chỉ kêu với người **đang mở ứng dụng**. Người trực phần lớn thời gian
không mở nó, nên một phiếu gửi lúc 21 giờ nằm im tới sáng hôm sau — và điều tệ
hơn là *không ai biết rằng nó đã nằm im*. Hệ thống trông hoàn toàn bình thường.

Nên có thêm hai đường thư, và chúng trả lời hai câu hỏi khác nhau:

| Thư | Trả lời | Nhịp |
|---|---|---|
| `send_support_ticket_email` | "vừa có người hỏi" — một **sự kiện** | mỗi phiếu mới |
| `send_support_backlog_email` | "đang có bao nhiêu câu chưa trả" — một **trạng thái** | tối đa 4 giờ một lần |

**Chỉ phiếu MỚI mới gửi thư, lượt trả lời qua lại thì không.** Một cuộc trao đổi
có thể là hàng chục lượt trong mười phút; gửi thư mỗi lượt thì hộp thư người
trực thành cái loa, và cái loa nào cũng bị tắt tiếng sau vài ngày. Nhịp trả lời
được che bởi cảnh báo tồn đọng.

**Thư KHÔNG chép nội dung người dùng viết.** Chỉ tiêu đề phiếu, tên người gửi,
và đường liên kết. Nội dung trao đổi là dữ liệu của tenant; ai cần đọc thì bấm
vào, và lúc đó việc đọc có kiểm soát truy cập. Cả hai thư dùng `loggable=True`,
tức chúng rơi vào nhật ký khi chưa cấu hình SMTP — lý do nữa để không chở nội
dung.

**Chỉ gửi tới địa chỉ đã xác minh** (`email_verified_at IS NOT NULL`). Một địa
chỉ chưa ai chứng minh là có thật vẫn có thể là địa chỉ của người khác.

> **Một lỗi mà bộ test bắt được ngay lượt chạy đầu.** Câu truy vấn lấy địa chỉ
> viết là `id = ANY(%s)` với một danh sách chuỗi, còn `users.id` là `uuid`.
> Postgres từ chối bằng **lỗi**, không phải bằng 0 dòng — và lỗi đó bị `try/except`
> ở chỗ gọi nuốt mất. Hậu quả: **không thư nào được gửi bao giờ**, lặng lẽ, đúng
> thứ tính năng này sinh ra để chống. Bản đúng là `ANY(%s::uuid[])`.

## 11. Tồn đọng: đo cái gì, và ngưỡng nào

`app/support_backlog.py`. Hai ngưỡng, quan hệ **hoặc**:

| Ngưỡng | Giá trị | Bắt kiểu hỏng nào |
|---|---|---|
| `THRESHOLD_HOURS` | 5 giờ | một phiếu bị bỏ quên cả buổi |
| `THRESHOLD_MESSAGES` | 10 lời nhắn | một đợt nhiều người cùng hỏi mà không ai kịp trả |

Chỉ có ngưỡng giờ thì một đợt mười người hỏi trong nửa tiếng vẫn lọt, vì chưa
câu nào chờ đủ lâu. Chỉ có ngưỡng số lượng thì một phiếu duy nhất bị bỏ quên cả
ngày vẫn im.

### "Đang chờ" nghĩa là gì

Một phiếu đang chờ khi **lời nhắn cuối cùng của con người** trong đó là của
người dùng. Ba chi tiết, cả ba đều là chỗ dễ đếm sai:

* **Lời của trợ lý (`author_kind = 'bot'`) KHÔNG tính.** Trợ lý luôn trả lời
  ngay, nên nếu tính nó thì không phiếu nào "đang chờ" bao giờ — cảnh báo im
  lặng vĩnh viễn và trông y hệt một kênh hỗ trợ chạy tốt. Đây là cái bẫy chính
  của cả mô-đun, và nó có một test riêng.
* **Đếm theo lời nhắn cuối, không theo `status`.** Trạng thái là thứ người ta
  bấm tay và quên bấm; lời nhắn thì không nói dối được.
* **Phiếu `resolved`/`closed` không tính**, kể cả khi người dùng nói lời cuối.

### Thư luôn mang CON SỐ

```
Phiếu đang chờ trả lời:      7
Phiếu cũ nhất chờ:           9.5 giờ
Lời nhắn chưa được trả lời:  12
```

Câu "kênh hỗ trợ đang có tồn đọng" mà không kèm số thì người đọc vẫn phải mở hệ
thống ra mới quyết định được có nên bỏ dở việc đang làm hay không — tức là thư
chưa làm xong việc của nó. Số phiếu chờ nằm **ngay dòng tiêu đề**, vì người ta
lọc hộp thư bằng dòng tiêu đề.

Thư cũng chỉ nêu **ngưỡng đã vượt**, không nêu cả cái chưa vượt: kể thêm một
con số chưa tới ngưỡng là làm loãng lý do gửi thư.

### Nhịp và khoảng lặng

- Beat `support-backlog-every-30min` (`app/saas_tasks.sweep_support_backlog`).
  Nửa tiếng vì cảnh báo nói "đã chờ quá 5 giờ" — độ trễ phát hiện phải nhỏ hơn
  hẳn 5 giờ, nếu không câu chữ trong thư là một lời nói dối làm tròn.
- `RESEND_COOLDOWN_S = 4 giờ`, giữ ở Redis. **Không có Redis thì VẪN GỬI**:
  hỏng kiểu "thừa một thư" thì người ta thấy ngay và kêu; hỏng kiểu "im lặng"
  đúng là thứ cảnh báo này sinh ra để chống.
- `platform_wide=True` là **bắt buộc**. Lượt quét đọc phiếu của mọi tổ chức;
  chạy trong phạm vi một tenant thì RLS trả về 0 dòng và nó báo "không có tồn
  đọng" một cách hoàn hảo, mãi mãi.

## 12. Huy hiệu và pop-up trong console quản trị

`GET /api/v1/admin/attention` → `{counts: {"<href>": n}}`, khoá **chính là**
`href` của mục trong `ADMIN_NAV`. Không có bảng tên thứ hai: hai bảng song song
là chỗ chắc chắn lệch nhau khi thêm mục, và lệch im lặng (huy hiệu chỉ đơn giản
không hiện).

### Chỉ đếm VIỆC ĐANG CHỜ, không đếm tồn kho

Mọi con số phải thoả một điều kiện: **về 0 khi ai đó làm xong việc**. Đếm tồn
kho — bao nhiêu người dùng, bao nhiêu nhãn — thì huy hiệu luôn sáng, và trong
một tuần người ta thôi nhìn nó. Lúc đó nó tệ hơn là không có.

| Mục | Đếm gì |
|---|---|
| `/admin/support` | phiếu mà lời nhắn cuối của con người là của người dùng |
| `/admin/vocabulary` | đề xuất phương ngữ `status = 'pending'` |
| `/admin/legal` | bản nháp `draft` / `in_review` / `approved` |
| `/admin/tenants` | lời mời chưa nhận, chưa thu hồi, chưa hết hạn |
| `/admin/resources` | số cảnh báo đang mở (lấy thẳng từ `collect_resources`) |

Mục nào không định nghĩa được "việc cần làm" thì **không có huy hiệu**, và như
thế là đúng.

### Huy hiệu là trạng thái, pop-up là sự kiện

`useAdminAttention` nổ pop-up **chỉ khi con số tăng so với lần đo trước**:

- **lần đo đầu tiên im tuyệt đối** — mở console lên mà nhận năm pop-up cho năm
  việc có từ hôm qua là báo sai; `seen` khởi tạo `null` chứ không phải `{}`
  chính là để phân biệt "chưa đo lần nào" với "đo rồi, tất cả bằng 0";
- **giữ nguyên thì im** — nếu không, mỗi 30 giây một cái y hệt;
- **giảm thì im** — việc vừa làm xong không phải tin cần cắt ngang ai;
- **một lượt hỏi hụt không xoá trắng huy hiệu** — về 0 nghĩa là "xong hết", và
  đó là một lời nói dối.

Cả năm tính chất có test (`useAdminAttention.test.tsx`).

> **Hai lỗi mà test bắt được:**
> 1. `useToast()` dựng object mới mỗi lần dựng lại, nên để nó trong mảng phụ
>    thuộc của `refresh` làm `useEffect` chạy lại sau **mọi** lần dựng — mỗi
>    lần đặt state kéo thêm một lượt gọi máy chủ. Sửa bằng `toastRef`.
> 2. `useToast()` **ném** khi thiếu `<ToastProvider>`. Ở một hook nằm trong VỎ
>    console, điều đó không tắt mất pop-up — nó làm **trắng cả console**. Nay
>    bọc `try/catch`: thiếu provider thì mất pop-up, huy hiệu vẫn chạy.

## 13. Kiểm chứng (phần II)

```bash
pytest tests/test_support_backlog.py -q     # 13 test
pytest tests/test_admin_attention.py -q     # 5 test (mỗi truy vấn huy hiệu chạy được trên lược đồ thật)
pytest tests/test_audit_coverage.py -q      # 14 test
npx vitest run src/hooks/__tests__/useAdminAttention.test.tsx   # 6 test
```
