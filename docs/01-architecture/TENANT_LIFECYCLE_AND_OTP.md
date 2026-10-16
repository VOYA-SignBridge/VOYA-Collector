# Vòng đời tenant, RLS mở rộng, và mã một lần (OTP)

*2026-08-07 — tiếp nối `TENANT_ISOLATION.md` (A1–A4, B1–B4).*

Tài liệu này ghi ba việc: **(1)** API vòng đời tenant và cách một người vào được
một tenant, **(2)** mở RLS sang `users` và `training_jobs`, **(3)** mã một lần
cho email và số điện thoại.

Trước đó nền tảng có cơ chế cô lập đã kiểm chứng nhưng **không có đường nào tạo
tenant thứ hai** — nên mọi khẳng định về cô lập đều dựa trên scope tổng hợp
trong test, chưa bao giờ trên hai tenant thật. Việc đầu tiên ở đây là mở khoá
phép thử đó.

---

## 1. Ai vào được tenant nào — hai đường, không có đường thứ ba

| Đường | Ai làm | Ghi ở đâu |
|---|---|---|
| Người vận hành nền tảng gắn một tài khoản sẵn có | `is_admin` | `add_member` |
| Một người nhận lời mời lúc đăng ký | chính người đó | `consume_invitation` |

**Không có tự đăng ký tổ chức.** Nền tảng này phục vụ các cơ sở có tên; một
tenant là một quan hệ có thật với một trường, không phải thứ mà người gọi vô danh
tạo ra được. Quyết định đó loại bỏ cả một nhóm lạm dụng (spam tenant, vét cạn tài
nguyên) với giá là một thao tác thủ công khi onboard.

### 1.1 Hai thẩm quyền, không bao giờ trộn

- **Người vận hành nền tảng** (`users.is_admin`) — tạo/xoá tenant, chuyển tài
  khoản giữa các tenant.
- **Quản trị viên tenant** (`tenant_members.role = 'admin'`) — quản lý thành viên
  và lời mời **của đúng tenant đó**.

Hai dependency riêng biệt, có chủ ý. Một hàm `is_authorized` gộp cả hai là cách
mà "admin của tenant A" dần dần có quyền ở tenant B: kiểm tra vẫn xanh, và ở chỗ
gọi không có gì cho thấy thẩm quyền nào đã thoả mãn nó.

Ngoại lệ duy nhất hai bên gặp nhau: người vận hành nền tảng qua được
`require_tenant_admin`, để còn sửa được một tenant mà admin duy nhất đã rời đi.
Viết đúng **một lần**, trong `require_tenant_admin`, không suy ra lại ở từng
endpoint.

### 1.2 Lời mời — token không bao giờ được lưu

`tenant_invitations` giữ `token_hash = SHA-256(token)`, không giữ token. Trả về
đúng một lần, trong đúng một response. Mất thì thu hồi và mời lại — đó là đánh
đổi đúng: một token máy chủ đọc lại được là một token kẻ tấn công cũng đọc được.

Bốn từ chối khác nhau, mỗi cái chặn một tình huống khác nhau:

| Từ chối | Chặn cái gì |
|---|---|
| token không tồn tại | đoán mò, hoặc link của tenant đã xoá |
| hết hạn / đã thu hồi / đã dùng | phát lại link cũ |
| **email không khớp** | link bị chuyển tiếp |
| tenant không hoạt động | quan hệ đã kết thúc trong lúc link đang bay |

Cái thứ ba là cái hay bị bỏ. Lời mời **gọi tên một người**; để ai cầm URL cũng
vào được thì việc chuyển thư trở thành yếu tố xác thực, mà chuyển thư không phải
yếu tố xác thực.

Mời lại một địa chỉ đang có lời mời sống sẽ **thay thế** nó. Hai token hợp lệ cho
một chỗ nghĩa là thu hồi một cái vẫn còn một đường vào — và một *partial unique
index* bắt cơ sở dữ liệu từ chối, chứ không tin vào việc hàm này là người ghi duy
nhất.

### 1.3 Đăng ký

`RegisterRequest` **không có** trường `tenant_id`, chỉ có `invitation_token`. Nếu
người gọi tự đặt được tenant thì họ vào được bất kỳ tenant nào đoán ra id — mà id
tenant nằm trong URL. Có test ghìm điều này: gửi thêm khoá `tenant_id` vẫn rơi
vào tenant công khai.

Lời mời được kiểm **trước** khi tạo tài khoản. Tạo trước rồi mới phát hiện token
hỏng sẽ để lại một tài khoản thật mắc kẹt ở tenant công khai — và người dùng thấy
lỗi sẽ thử lại, rồi đụng đúng cái username mình vừa chiếm.

### 1.4 Lỗ hổng tìm thấy khi dựng phép thử hai tenant

`classes` tham chiếu `dialects` bằng khoá ngoại **hợp**:
`(tenant_id, dialect) → dialects(tenant_id, dialect_id)`.

Nên một tenant không có dòng dialect nào của riêng nó **không chứa nổi một lớp
nào**. `create_tenant` ban đầu chỉ tạo dòng trong `tenants` — cho ra một tenant
nhìn bình thường trong danh sách của người vận hành và từ chối mọi lệnh ghi, kèm
lỗi khoá ngoại nhắc tới một bảng mà người vận hành chưa từng nghe tên.

Khoá hợp đó là thiết kế **đúng**: nó chính là thứ ngăn lớp của tenant B trỏ vào
dialect của tenant A. Nhưng nó khiến "tạo tenant" và "cho tenant một danh mục"
là **một** thao tác, không phải hai. `create_tenant` nay gọi
`clone_catalog_to_tenant`.

Lỗi này chỉ lộ ra vì phép thử hai tenant ghi dữ liệu thật. Không bộ test nào của
mục 1 bắt được — chúng chỉ kiểm tra bảng `tenants` và `tenant_members`.

---

## 2. RLS trên `users` và `training_jobs`

### 2.1 Rò rỉ chứng minh được ở `training_jobs`

```sql
SELECT * FROM training_jobs ORDER BY created_at DESC LIMIT %s
```

`list_training_jobs` — không có vị từ tenant nào. Đúng chỉ vì có đúng một tenant.

Kèm theo, `SQL_UPSERT_TRAINING_JOB` **chưa từng ghi `tenant_id`**, nên mọi job
rơi vào giá trị mặc định của cột. Vô hại với một tenant; sai với hai; và một khi
bảng có `WITH CHECK` thì thành lỗi thẳng, vì policy từ chối một dòng có tenant
khác scope đang ghi. Cả hai đã sửa; `upsert_training_job` lấy tenant từ **scope
hiện hành**, không từ tham số — cùng lý do `apply_scope` đọc ContextVar: người
gọi không được nộp job dưới tên một tenant khác.

### 2.2 `users` — bảo đảm hẹp hơn, và nói thẳng ra

Xác thực xảy ra **trước** khi biết tenant:

```
request đến ──> giải mã token ──> đọc users.tenant_id ──> ĐẶT scope
```

Lệnh đọc **quyết định** scope không thể bị lọc bởi chính scope đó. Policy đặt ở
đó sẽ so với một GUC chưa đặt, khớp không dòng nào, và không ai đăng nhập được.

Nên `app/auth.py` và `tenant_middleware._tenant_of_user` chạy trong system scope,
và **RLS trên `users` không ràng buộc chúng**. Cái nó ràng buộc là mọi lệnh đọc ở
tầng dữ liệu: các phép JOIN trong `metadata_db` gắn tên người đóng góp vào một
mẫu hay một job, phần tra username của bảng hoạt động, và `created_by` của danh
sách dialect. Đó là những chỗ một `auth_user_id` chéo tenant sẽ giải ra một cái
tên thật; có policy thì nó giải ra NULL.

Đó là một bảo đảm **thật** và **có giới hạn**. Ghi ra đây để không ai đọc "RLS
trên users" thành nhiều hơn thực tế.

Cả tám lệnh trong `auth.py` đi qua **một** context manager duy nhất
(`_identity_cursor`), không phải tám chỗ rải rác. Chuỗi lý do nằm trong docstring
của nó, và `auth.py` + `tenant_middleware.py` đã được thêm vào allowlist ranh giới
trong `test_tenant_isolation.py` — nơi test bắt một call site thứ chín xuất hiện.

### 2.3 Bảng RLS: 3 → 5

`samples`, `classes`, `raw_uploads`, **`training_jobs`**, **`users`**.

Tám bảng còn lại mang `tenant_id` là dữ liệu tham chiếu, chỉ tới được qua các
đường đã join vào một trong năm bảng này.

---

## 3. OTP cho email và số điện thoại

Mã sáu chữ số là **bí mật yếu** có chủ ý — phải gõ được từ một tin nhắn. Mọi thứ
ở đây tồn tại để cái yếu đó sống sót được.

### 3.1 Ba ràng buộc bạn đặt, và chúng được thực thi ở đâu

| Ràng buộc | Thực thi |
|---|---|
| Log **không** được lưu mã | `app/otp.py` chỉ log purpose + destination **đã che**; có test bắt lỗi bằng cách quét `caplog` cho chuỗi mã |
| OTP cho **cả** email lẫn SĐT | `channel IN ('email','sms')`, cùng một bảng, cùng một luồng |
| Mã đổi kênh giữa chừng | phát mã mới **đóng** mã cũ; partial unique index bắt DB từ chối hai mã sống |

### 3.2 Vì sao băm mã khác băm token

`app/tokens.py` cố ý có **hai** hàm, đặt cạnh nhau, tên nói rõ cái nào là cái nào:

- `hash_link_token` — SHA-256 thường. Token 32 byte không có từ điển để duyệt.
- `hash_code` — **HMAC** với *pepper* nằm **ngoài** cơ sở dữ liệu.

Một mã sáu chữ số có ~20 bit entropy. Băm thường ở đây là **đồ trang trí**: ai đọc
được bảng sẽ dựng đủ một triệu digest trong chưa tới một giây và đảo ngược mọi mã
đang sống. Pepper là thứ khiến "chiếm được cơ sở dữ liệu" chưa đủ.

Thiếu pepper thì `hash_code` **ném lỗi**, không tụt xuống băm thường. Một sự tụt
hạng âm thầm cho ra hệ thống nhìn từ ngoài y hệt và không bảo vệ gì cả.

`hash_code` buộc **purpose** và **subject** vào thông điệp. Không phải để giấu, mà
để **phân tách miền**: một mã bắt được lúc xác minh email không được đồng thời
thoả mãn yêu cầu đặt lại mật khẩu của cùng tài khoản đó.

### 3.3 Tình huống bạn nêu: xin qua email rồi quay lại chọn điện thoại

Ba khả năng, chỉ một đúng:

1. Cả hai mã còn sống — mã email nằm trong hộp thư và vẫn mở được tài khoản rất
   lâu sau khi người kia đã chuyển kênh. **Đây là cách hay gặp và nó sai.**
2. Từ chối đổi cho tới khi cái đầu hết hạn — an toàn, nhưng người dùng đọc thành
   "hệ thống hỏng" và cứ thử lại.
3. **Phát mã mới đóng mã cũ.** Người đó có đúng một mã sống, trên kênh họ vừa
   chọn.

`issue()` làm (3). Partial unique index `(user_id, purpose) WHERE consumed_at IS
NULL` khiến cơ sở dữ liệu từ chối (1) kể cả khi một người viết mã sau này quên.

### 3.4 Đoán mò bị **chặn**, không phải bị làm chậm

Một triệu mã và số lần thử không giới hạn là bài toán đã giải với kẻ tấn công.
Bộ đếm nằm **trên dòng dữ liệu**, nên nó sống qua restart và không reset được
bằng cách mở kết nối mới. Bộ đếm tăng **trước** khi so sánh: nếu tiến trình chết
giữa chừng thì lần thử vẫn bị tính — hỏng hóc phải cho ra *ít hơn* một lần đoán,
không bao giờ *nhiều hơn*.

Mọi kiểu thất bại trả về **cùng một** từ chối: hết hạn, sai mã, và không hề có
challenge nào đều giống nhau. Phân biệt được chúng sẽ cho người cầm một địa chỉ
bị lộ biết liệu có một yêu cầu đặt lại đang bay hay không.

### 3.5 SMS chưa cấu hình — và thành thật về điều đó

Không có nhà cung cấp SMS trên hệ thống này. Hai lối tắt đều bị **từ chối**:

- **Log mã thay vì gửi.** Chế độ "dev" quen thuộc. Nó đẩy mọi OTP vào Loki, nơi
  nhiều người đọc được hơn cơ sở dữ liệu — trong khi cả `app/otp.py` tồn tại để
  mã chỉ nằm ở đúng hai chỗ: điện thoại người nhận, và không đâu khác. Một tiện
  nghi cho dev mà vi phạm đúng quy tắc cứng của hệ thống thì không phải tiện nghi.
- **Trả về thành công.** Rồi `verify_phone` trông như chạy, không ai nhận được
  gì, và lỗi hiện ra dưới dạng "mã không bao giờ tới" rất lâu sau lần triển khai
  gây ra nó.

Nên `send_sms` **ném lỗi**, và endpoint từ chối kênh SMS **trước khi** đúc mã —
đúc một mã không thể giao được sẽ đốt mất cooldown và khiến tài khoản không thử
lại qua email được trong một phút.

### 3.6 Khôi phục tài khoản không tiết lộ gì

`/auth/recover/*` là endpoint vô danh, nên **mọi** response phải như nhau: tài
khoản có tồn tại hay không, địa chỉ có khớp hay không, gửi có được hay không.
Danh sách tài khoản của một chương trình giáo dục đặc biệt đúng là thứ không được
phép vét cạn.

Giá phải trả là thật: người gõ nhầm địa chỉ nhận được một câu "đã gửi mã" vui vẻ
và không có mã nào. Đó là đánh đổi tiêu chuẩn, và câu chữ nói "nếu tài khoản tồn
tại" để không chủ động đánh lừa.

Ngoại lệ duy nhất được nêu rõ: `too_many_attempts`. Nó nói với người dùng hợp lệ
rằng hãy xin mã mới, và nói với kẻ tấn công đúng một điều — rằng họ đã thua.

### 3.7 "Đặt lại mật khẩu" nghĩa là gì, viết một lần

`_apply_password_reset` gom bốn lệnh không được phép trôi dạt khỏi nhau: đổi mật
khẩu, huỷ mọi link đặt lại, **giết mọi phiên**, và **tiêu mọi mã một lần đang
sống**. Hai đường gọi nó — luồng link qua email và luồng mã. Một bản sao thứ hai
chính là cách một trong hai đường đổi mật khẩu mà quên giết phiên.

---

## 3bis. Một lỗi triển khai tìm được nhờ chính comment của tài liệu này

`_split_sql_statements` trong `app/sot/reader_sync.py` là **mã sản xuất**: dòng
331 dùng nó để áp schema lúc triển khai. Nó tôn trọng chuỗi `'...'` và khối
`$tag$...$tag$`, nhưng **bỏ qua comment SQL**.

Nên một dấu `;` trong một comment `--` cắt câu lệnh làm đôi. Tôi phát hiện ra vì
comment tôi viết cho ràng buộc `tenant_invitations_accept_is_complete` có câu
*"…là một trạng thái có thật; một accepter không có thời điểm chấp nhận thì
không"* — tiếng Anh bình thường, đúng chỗ người ta hay giải thích một đánh đổi,
và đúng chỗ dấu chấm phẩy hay xuất hiện.

Kiểu hỏng đáng chú ý: **không phải lỗi cú pháp lúc review**. Bản export nhìn vẫn
đúng; lúc triển khai thì áp **nửa** câu `CREATE TABLE`. Cái bắt được nó là một
test đếm — schema round-trip ra 108 câu lệnh thay vì 107.

Đã sửa bộ tách để bỏ qua `--` và `/* */`, kèm ba test: chấm phẩy trong comment
dòng, trong comment khối, và `--` **bên trong** một chuỗi ký tự (là dữ liệu, không
phải comment — coi nó là comment sẽ nuốt luôn dấu nháy đóng).

---

## 4. Điều tài liệu này *không* khẳng định

- **Không khẳng định RLS bảo vệ được đường xác thực.** Mục 2.2 nói rõ: tầng danh
  tính được miễn trừ và **buộc phải** thế. Ai đọc "RLS trên users" thành "không
  ai đọc được users của tenant khác" là hiểu sai.
- **Không khẳng định Celery cô lập theo tenant.** Task vẫn chạy ở system scope.
  `upsert_training_job` khi ở system scope sẽ lấy tenant từ dòng dữ liệu, hoặc rơi
  về tenant khởi tạo nếu dòng đó chưa có. Truyền tenant vào thông điệp task là
  việc còn nợ.
- **Không khẳng định SMS hoạt động.** Nó ném lỗi. Xem 3.5.
- **Không khẳng định email đã xác minh là bắt buộc.** `email_verified_at` được
  ghi nhận nhưng chưa endpoint nào đòi nó. Bật cưỡng chế là một quyết định vận
  hành: 10 tài khoản hiện có đều chưa xác minh, nên bật ngay sẽ khoá tất cả.
- **Không khẳng định tám bảng còn lại được cô lập.** Chúng mang `tenant_id` và
  không có policy.
- **Không khẳng định chống được người trong cuộc có quyền DB.** Ai có
  `MIGRATION_DATABASE_URL` bỏ qua được toàn bộ.

---

## 5. Vận hành

```powershell
# Bắt buộc trước khi bật OTP. Không có mặc định trong mã: một giá trị mặc định
# nằm trong source là giá trị công khai, tức là không có pepper.
$env:OTP_PEPPER = "<32+ ký tự ngẫu nhiên>"
```

| Biến | Mặc định | Ý nghĩa |
|---|---|---|
| `OTP_PEPPER` | *(rỗng — bắt buộc đặt)* | khoá HMAC cho mã, giữ ngoài DB |
| `OTP_TTL_MINUTES` | 10 | mã sống bao lâu |
| `OTP_MAX_ATTEMPTS` | 5 | số lần đoán sai trước khi mã chết |
| `OTP_RESEND_COOLDOWN_SECONDS` | 60 | bảo vệ **người nhận**, không phải endpoint |
| `INVITATION_TTL_HOURS` | 168 | link mời sống một tuần |

**Xoay pepper sẽ vô hiệu mọi mã đang sống.** Đó là hành vi đúng, nhưng hãy làm
lúc vắng người: ai đang giữa chừng một luồng xác minh sẽ phải xin mã mới.

---

## 6. Mặt giao diện — dựng 2026-08-09

Trước hôm nay ba luồng ở tài liệu này chỉ chạy được bằng `curl`. Ba trang mới:

| Tuyến | Trang | Cổng | Gọi tới |
|---|---|---|---|
| `/verify` | `VerifyContactPage` | đã đăng nhập | `GET /auth/verification-status`, `POST /auth/verify/{send,confirm}` |
| `/recover` | `AccountRecoveryPage` | công khai | `POST /auth/recover/{start,confirm}` |
| `/invitation` | `InvitationPage` | công khai | `POST /tenants/invitations/inspect` |

Kèm một endpoint mới: **`GET /auth/verification-status`**. Tách riêng chứ không
nới `UserOut`, vì `UserOut` là phản hồi của login, register, refresh **và**
`/me` — nới nó là thêm một lượt đọc cột vào mọi request đã xác thực để phục vụ
đúng một trang. Trả về địa chỉ, hai cờ đã-xác-minh, `resend_cooldown_seconds`,
`code_ttl_minutes`, `sms_available`.

Số điện thoại trả về **nguyên vẹn**. Nó là của chính người gọi, người đã xác
thực, và một nửa số không trả lời được câu hỏi duy nhất trang đó tồn tại để
hỏi: "có còn đúng số này không?".

### 6.1 Bẫy ăn mòn lượt thử — ĐÃ VÁ Ở API (2026-08-09)

`confirm_verification_code` dò `verify_phone` **trước**, rồi mới tới
`verify_email`. Hệ quả không hiển nhiên:

> Nếu cả hai thử thách cùng sống, mỗi lần nộp **mã email sai** cũng tiêu một
> lượt thử của thử thách điện thoại. Năm lần là thử thách điện thoại chết vì
> `too_many_attempts` dù người dùng chưa gõ sai chữ nào cho nó.

Bản trước của mục này kết luận *"chỗ chặn được là giao diện"*, và ghi lại rằng
một client thứ hai sẽ dính lại. Giờ **`/verify/confirm` nhận tham số `purpose`
không bắt buộc**:

```jsonc
POST /api/v1/auth/verify/confirm
{ "code": "123456", "purpose": "verify_email" }   // chỉ thử ĐÚNG cái này
{ "code": "123456" }                              // lối dò cũ, giữ nguyên
```

**Không bắt buộc, có chủ ý.** Client viết trước khi tham số này tồn tại vẫn
chạy y như cũ. Cái giá của lối cũ giờ là một **chi phí đã biết** chứ không phải
một bất ngờ: có một test ghim thẳng nó
(`test_without_a_purpose_the_probe_still_erodes_both`), nên nếu ai đó đổi hành
vi mặc định thì test đỏ chứ không phải người dùng phát hiện.

**`purpose` là ràng buộc, không phải gợi ý.** Nêu sai mục đích thì bị từ chối,
không rơi về lối dò — một gợi ý thì không bảo vệ được hạn mức mà nó sinh ra để
bảo vệ. `reset_password` không nằm trong tập giá trị hợp lệ và bị chặn ngay ở
lớp schema (422): mã đó được tiêu ở `/recover/confirm` **cùng lúc với mật khẩu
mới**, nên nhận nó ở đây là đốt thử thách mà không ai chọn được mật khẩu nào.

**Giao diện vẫn giữ đúng một luồng mở, và hai lớp này không thừa nhau.** Hai ô
nhập mã cùng mở là một màn hình khó dùng, chứ không chỉ là một vấn đề hạn mức.
Nhưng lớp giao diện chỉ bảo vệ được người đi qua *trang đó* — lớp API bảo vệ
mọi người gọi.

Ghim ở hai phía: `test_otp.py::TestNamingTheChallengeBeingAnswered` (5 test) và
`VerifyContactPage.test.tsx` — "Nói rõ mã trả lời cho thử thách nào" (2 test).

### 6.2 Mã lời mời đi trong fragment, không phải query string

Đường liên kết **do máy chủ dựng** và trả về trong phản hồi tạo lời mời:

```jsonc
POST /api/v1/tenants/{id}/invitations
→ {
    "token": "…",
    "accept_url": "https://<máy chủ>/voya/invitation#token=<mã>",
    "email_sent": true
  }
```

Dấu thăng, không phải dấu hỏi. Trình duyệt **không gửi phần sau dấu thăng lên
máy chủ**, nên mã không đọng ở nhật ký truy cập nginx, không đi qua proxy, và
không rò qua header `Referer` khi người nhận bấm sang trang khác. Cùng lý do
`inspect` là POST chứ không phải GET (§1.2).

Mã ở query string vẫn được chấp nhận — thư mời cũ có thể ở dạng đó, và một
liên kết chết tệ hơn một liên kết kém kín — nhưng trang gỡ nó khỏi thanh địa
chỉ bằng `replaceState` ngay khi đọc xong. Muộn còn hơn không: nó chặn được
phần lịch sử trình duyệt và phần `Referer`.

Từ trang mời, mã sang biểu mẫu đăng ký qua **state của router**, không qua URL
lần thứ hai. State không sống qua một lần tải lại trang, và đó là hành vi
đúng: tải lại thì phần mời biến mất và biểu mẫu quay về đăng ký thường, thay vì
mang theo một mã người dùng không còn nhìn thấy.

#### Vì sao máy chủ dựng liên kết, không phải trình duyệt (đổi 2026-08-09)

Trước đây `AdminTenantsPage` tự ghép chuỗi từ `window.location.origin`, đường
dẫn `/invitation` và `VITE_BASE_PATH`. Nghĩa là **tên một tuyến của giao diện
sống ở hai kho mã cùng lúc**. Đổi tên tuyến ở một nơi thì mọi lời mời phát ra
sau đó đều chết — hỏng lặng lẽ, hiện ra vài ngày sau dưới dạng một trang trắng
trên máy người lạ, tức là trên đúng người ít có khả năng báo lại nhất.

`public_url.frontend_url(request, "invitation", fragment=f"token={token}")` đặt
tên tuyến ở một chỗ, và nó cũng biết hai thứ trình duyệt không biết chắc: tên
miền công khai **đã được duyệt** (Host là thứ kẻ tấn công điều khiển được — một
`Host: evil.example` giả mạo sẽ gửi cho nạn nhân một lời mời HỢP LỆ trỏ vào
trang của kẻ khác), và đường dẫn con của bản triển khai.

Ghim cả ba: là URL đầy đủ, mã nằm sau dấu thăng (`"?" not in url`), và một Host
không nằm trong danh sách duyệt **không** chọn được tên miền
(`TestTheLinkAndTheMail`, `test_tenant_lifecycle.py`).

#### Thư mời gửi tự động, và `email_sent` nói thật

`send_invitation_email` chạy ngay trong lượt tạo. Nó dùng `loggable=False` —
**khác** với liên kết đặt lại mật khẩu ngay cạnh nó, dù hai mã cùng độ mạnh.

Khác nhau ở đường thất bại. Lượt đặt lại mật khẩu do một người đang ngồi trước
màn hình yêu cầu; không có SMTP thì dòng log là cách duy nhất để thử được luồng
đó. Lời mời thì do quản trị viên phát ra, **và họ đang cầm liên kết trong tay**
— `create_invitation` vừa trả nó về. Ghi một thông tin đăng nhập vào-tổ-chức
vào Loki, nơi nhiều người đọc được hơn cơ sở dữ liệu, không mua được gì cả.

Nên gửi hỏng thì hàm ném lỗi, endpoint bắt lấy, trả `email_sent: false`, và lời
mời **vẫn hợp lệ** — nó đã nằm trong bảng và liên kết đã ở trong phản hồi. Huỷ
lời mời chỉ vì SMTP chưa cấu hình là vứt đi một thứ hoàn toàn dùng được.

Trang quản trị đổi hẳn câu chữ theo cờ này. Nói "đã gửi" khi không gửi được là
để người được mời ngồi đợi một lá thư không tồn tại, còn quản trị viên thì
không biết mình phải gửi tay.

### 6.3 Trang khôi phục không được nói điều máy chủ đang giấu

`/recover/start` trả **một câu duy nhất** cho mọi kết cục (§3.6). Giao diện dễ
hoàn tác toàn bộ công sức đó chỉ bằng một dấu tích xanh hoặc một câu "đã gửi mã
tới bạn". Nên `AccountRecoveryPage` hiện **nguyên văn** câu của máy chủ, và có
test ghim rằng những câu khẳng định kia không xuất hiện.

### 6.4 Đồng hồ chờ lấy từ máy chủ

`useResendCountdown` tính từ `Date.now()`, không phải bằng bộ đếm giảm dần mỗi
nhịp — timer của tab nền bị trình duyệt hạ xuống một nhịp mỗi phút, và khoá màn
hình thì dừng hẳn, nên bộ đếm giảm dần sẽ báo còn 59 giây khi thực tế đã hết.

Đó vẫn chỉ là lớp lịch sự. Khi máy chủ trả 429 kèm "vui lòng đợi N giây", giao
diện lấy **N của máy chủ** và mở ô nhập mã ra — 429 nghĩa là một mã vẫn đang
sống trong hộp thư của họ, nên giữ nguyên màn hình xin mã là bắt họ đứng trước
một nút không bấm được.
