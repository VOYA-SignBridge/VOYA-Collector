# Quên mật khẩu — một cửa, ba bước

*Viết lại 2026-08-10. Bản trước có hai cửa và một biểu mẫu gộp bốn ô.*

---

## 1. Vì sao phải viết lại

Bản trước để hai đường khôi phục cạnh nhau trên màn hình đăng nhập:

| Đường | Gửi gì | Hỏng khi nào |
|---|---|---|
| `Quên mật khẩu?` → `/forgot-password` | đường liên kết vào email | mở thư trên điện thoại mà phiên ở máy tính; bộ lọc thư viết lại URL |
| `Khôi phục bằng mã` → `/recover` | mã sáu chữ số | không đọc được thư (nhưng mã đi được qua SMS) |

Bảng này đúng về mặt kỹ thuật và **vô dụng với người đang cần dùng nó**. Người
vừa quên mật khẩu không biết bộ lọc thư của trường có viết lại URL hay không —
đó là chi tiết của bên triển khai, và đem nó ra hỏi người dùng là đẩy một quyết
định kỹ thuật xuống cho người không có dữ kiện để quyết.

Ba chỗ hỏng nữa ở màn hình `/recover` cũ:

* **Nút "Tôi đã có mã rồi."** Mã chỉ ra đời khi ai đó bấm xin. Một cửa để tự
  khai là mình có mã sẵn mô tả một tình huống không tồn tại. Người chưa thấy mã
  cần nút **Gửi lại**, thứ đã có sẵn ngay bên dưới.
* **Bước hai hỏi lại tên đăng nhập.** Người dùng vừa gõ xong ở bước một đã bị
  hỏi lại đúng câu đó, không lý do.
* **Mã và mật khẩu mới trong cùng một biểu mẫu.** Gõ nhầm một chữ số của mã thì
  cái mất là cả một mật khẩu vừa nghĩ ra — vì máy chủ chỉ trả lời sau khi đã
  nhận đủ bốn ô.

## 2. Luồng hiện tại

Một liên kết duy nhất trên `/login`: **Quên mật khẩu?** → `/forgot-password`.
`/recover` chuyển hướng về đó (địa chỉ này đã đi ra ngoài trong thư).

```
Bước 1  Tên đăng nhập hoặc email  +  chọn kênh (email / tin nhắn)
          │  POST /auth/recover/start          → câu chung, luôn 200
          ▼
Bước 2  Ô mã sáu chữ số.  Tên đăng nhập hiện ở đây là NGỮ CẢNH chỉ-đọc,
        kèm nút "Đổi" quay lại bước 1.  Nút "Gửi lại" có đếm ngược.
          │  POST /auth/recover/verify         → vé sống 5 phút
          ▼
Bước 3  Mật khẩu mới + xác nhận.  Không còn ô mã.
          │  POST /auth/recover/confirm        → thu hồi mọi phiên
          ▼
        Xong.
```

## 3. Vì sao phải tách `verify` khỏi `confirm`

Máy chủ trước đây cố ý gộp: một endpoint chỉ kiểm mã sẽ cho biết mã nào đúng mà
không phải trả gì. Lập luận đó đúng về hình thức và **không sống nổi phép đo**:

* `/recover/confirm` cũ đã là một oracle rồi. Gửi một mật khẩu hợp lệ kèm một mã
  đoán bừa cho ra đúng thông tin ấy — chỉ tốn thêm 8 ký tự rác.
* Thứ thật sự chặn đoán mã không phải là "có mấy endpoint", mà là **năm lượt thử
  trên chính hàng thử thách** (`otp.verify`), cộng bộ đếm tần suất theo IP.

Nên khi tách, cái phải giữ nguyên là **ngân sách đoán**, không phải số endpoint:

> `/recover/verify` và `/recover/confirm` **dùng chung một xô tần suất**
> (`otp_recover_confirm`, 20 lượt/giờ/IP). Cho mỗi endpoint một xô riêng là tự
> nhân đôi số lần đoán mã chỉ vì đã tách biểu mẫu làm hai.

Ghim ở `TestRecoveryInTwoSteps` trong `backend/tests/test_otp.py`.

## 4. Vé đặt lại mật khẩu

JWT `typ = "pw_reset"`, sống 5 phút, ký bằng `SECRET_KEY` — cùng khuôn với vé
hai bước (`create_2fa_challenge`), và cùng lý do: nó sống ngắn và không cần thu
hồi, nên một bảng chỉ thêm việc phải dọn.

Ba tính chất phải giữ:

1. **Mã bị tiêu ngay ở `verify`**, không phải ở `confirm`. Một mã còn sống sau
   khi đã dùng là một mã nằm trong hộp thư chờ người khác đọc. Hệ quả nhìn thấy
   được: bỏ dở giữa bước 2 và bước 3 thì phải xin mã mới — đúng như Google.
2. **Vé không dùng thay access token được.** `_decode_token` từ chối mọi `typ`
   khác `"access"`. Đây chính là lỗ mà vé hai bước từng có (xem
   `SESSION_LIFECYCLE.md` §3.2): mọi token ký cùng một khoá, nên chữ ký hợp lệ
   chỉ chứng minh "hệ thống này phát ra nó", không chứng minh nó được phát ra
   **để làm gì**. Ghim ở `test_the_ticket_is_not_an_access_token` và chiều ngược
   lại ở `test_a_2fa_challenge_is_not_a_reset_ticket`.
3. **Vé hết hạn cho lời từ chối KHÁC với mã sai.** An toàn, vì cầm được vé đã
   chứng minh mã từng đúng — câu này không tiết lộ thêm gì. Nói "mã sai" ở đây
   sẽ đẩy người ta quay lại đọc một mã đã tiêu, việc duy nhất chắc chắn không
   cứu được họ. Giao diện đưa họ về **bước 1**, không phải bước 2, vì bước 2 lúc
   đó là ngõ cụt: không còn gì để nhập ở đó.

## 5. Điều màn hình không được nói

`/recover/start` trả **cùng một câu** cho mọi kết cục — gửi được, tài khoản
không tồn tại, gửi thất bại, đang trong thời gian chờ. Khác nhau thì đây thành
công cụ dò xem ai có tài khoản, và danh sách tài khoản của một chương trình giáo
dục đặc biệt đúng là thứ không được rò.

Hệ quả cho giao diện, và đây là chỗ dễ hoàn tác công sức của tầng dưới **một
cách im lặng**:

* Không dấu tích xanh.
* Không câu "đã gửi mã tới bạn" — đó là lời nói dối với người vừa gõ nhầm địa
  chỉ, và họ sẽ ngồi đợi một mã không bao giờ tới.
* Chỉ hiện nguyên văn câu có điều kiện của máy chủ: *"Nếu tài khoản tồn tại…"*

Ghim ở `describe('Không tiết lộ tài khoản có tồn tại hay không')` trong
`frontend/src/pages/__tests__/ForgotPasswordPage.test.tsx`.

## 6. Đường liên kết cũ

`POST /auth/forgot-password`, `POST /auth/reset-password` và trang
`/reset-password` **vẫn chạy** — những liên kết đã gửi đi phải còn dùng được.
Không màn hình nào gọi chúng nữa. `api/auth.ts::forgotPassword` mang một ghi chú
nói rõ điều đó, để lần sau không ai nối lại vào giao diện vì tưởng nó bị bỏ quên.

## 7. Kiểm chứng

| Tệp | Số test | Canh gì |
|---|---|---|
| `backend/tests/test_otp.py::TestRecoveryInTwoSteps` | 8 | vé, tiêu mã, hai chiều của cổng `typ`, đúng-một-đường-vào |
| `backend/tests/test_otp.py::TestRecoveryEndpointRevealsNothing` | 5 | hợp đồng một-lượt cũ vẫn sống |
| `frontend/…/ForgotPasswordPage.test.tsx` | 17 | ranh giới giữa ba bước + điều không được nói |

```bash
docker run ... voya_backend_test:latest python -m pytest tests/test_otp.py -q
npx vitest run src/pages/__tests__/ForgotPasswordPage.test.tsx
```
