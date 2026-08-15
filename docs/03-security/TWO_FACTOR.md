# Xác thực hai bước (2FA)

*Xây 2026-08-10. Mã: `app/totp.py`, `app/two_factor.py`, `app/routers/two_factor.py`,
`frontend/src/components/account/TwoFactorSection.tsx`.*

---

## 1. Vì sao tự viết TOTP thay vì dùng `pyotp`

Thuật toán RFC 6238 là ~20 dòng `hmac` + `struct`. Thêm một phụ thuộc đòi **dựng
lại ảnh Docker**, mà ảnh đó chống lưng 5 dịch vụ.

Đổi lại, `app/totp.py` được kiểm bằng **vector thử công bố trong chính RFC** —
RFC 4226 Phụ lục D (10 vector HOTP) và RFC 6238 Phụ lục B (6 vector TOTP). Đó là
đối chứng với một bên thứ ba, mạnh hơn hẳn một bộ test so mã với chính nó.

Hai chỗ dễ viết sai, cả hai đã ghim bằng test:

- **Cắt bit động** phải `AND 0x7fffffff` để bỏ bit dấu. Thiếu bước đó thì khoảng
  một nửa số mã sai — và sai không theo quy luật nào nhìn thấy được.
- **So sánh mã** dùng `hmac.compare_digest`. So bằng `==` thoát ra ở ký tự đầu
  tiên khác nhau, và thời gian thoát đó biến việc dò 6 chữ số thành việc dò từng
  chữ số một.

## 2. Bí mật MÃ HOÁ, mã khôi phục BĂM

Khác nhau vì mục đích khác nhau:

| | Cách lưu | Vì sao |
|---|---|---|
| bí mật TOTP | Fernet, khoá dẫn xuất từ `SECRET_KEY` | cần chính bí mật để tính lại mã; băm một chiều vô dụng |
| mã khôi phục | HMAC-SHA256 khoá bằng `SECRET_KEY` | chỉ cần trả lời "đúng hay sai" |

Mã khôi phục chỉ có ~50 bit entropy, nên **băm trần là không đủ** — một bảng tra
cứu là khả thi. Khoá nằm ngoài CSDL làm bản dump bị rò trở nên vô dụng; cùng lý
do `app/tokens.py` dùng pepper cho mã OTP.

> **Đánh đổi phải biết trước:** đổi `SECRET_KEY` làm mọi bí mật TOTP đã lưu không
> giải mã được nữa, và **toàn bộ người dùng phải đăng ký lại 2FA**. Quy trình
> xoay khoá bí mật phải xử lý bảng `user_totp` — hiện chưa có quy trình đó (xem
> `docs/10-issues/KNOWN_ISSUES.md`).

## 3. Vì sao hai bảng này KHÔNG có RLS

`user_totp` và `user_recovery_codes` **cố ý** không mang `tenant_id` và không nằm
trong `RLS_TABLES` — giống `refresh_tokens` và `password_reset_tokens`.

Lý do không phải là tiện: chúng được đọc **giữa chừng lúc đăng nhập**, tức trước
khi hệ thống biết người này thuộc tenant nào. Nếu có RLS, truy vấn kiểm 2FA sẽ
khớp **0 dòng** và hệ thống kết luận "người này không bật 2FA" — tức là **bỏ qua
lớp bảo vệ thứ hai trong im lặng**.

RLS ở đây **fail-OPEN**. Đó là lý do đủ để loại nó. (Không phải giả thuyết: đúng
dạng lỗi đó xảy ra hai lần trong ngày 2026-08-10 — mốc thu hồi phiên, và đường
đồng bộ đồng thuận.)

## 4. Bật là HAI bước

`begin_enrollment` chỉ ghi bí mật ở trạng thái **chưa xác nhận**;
`confirm_enrollment` mới bật.

Gộp làm một sẽ khoá người dùng ra khỏi tài khoản của chính họ khi ứng dụng xác
thực quét hỏng hoặc đồng hồ điện thoại lệch — và lúc đó họ không còn đường nào
quay lại. Giao diện phải **hiện đúng trạng thái đó**: đăng ký dở vẫn là "Chưa
bật". Ghim ở `test_dang_ky_do_KHONG_duoc_hien_thanh_da_bat`.

Gọi lại `begin_enrollment` khi đang dở sẽ **thay** bí mật cũ: người dùng quét
hỏng rồi bấm lại là chuyện thường, và giữ bí mật cũ khiến mã trên điện thoại
không bao giờ khớp.

## 5. Chống phát lại

Một mã TOTP sống 30 giây. Không ghi lại bước đã dùng thì người **nhìn trộm màn
hình** gõ lại đúng mã đó vẫn vào được — chính kịch bản 2FA sinh ra để chặn.

`user_totp.last_used_step` khoá cửa đó. Điều kiện nằm **trong** câu `UPDATE`, nên
hai yêu cầu song song không thể cùng thắng:

```sql
UPDATE user_totp SET last_used_step = %s
WHERE user_id = %s AND (last_used_step IS NULL OR last_used_step < %s)
RETURNING user_id
```

> **Lỗi đã mắc và đã sửa:** bản đầu ghi rồi **đọc lại** và so
> `last_used_step == step`. Lần gọi thứ hai thấy đúng giá trị mà lần gọi *thứ
> nhất* vừa ghi, nên nó kết luận thành công — **chống phát lại không hề chạy**.
> `RETURNING` trả lời đúng câu hỏi cần hỏi: "câu UPDATE NÀY có khớp dòng nào
> không". Ghim ở `test_CHONG_PHAT_LAI_trong_cung_buoc_thoi_gian`.

Cửa sổ lệch đồng hồ là **±1 bước** (±30 giây). Đặt 0 sẽ từ chối oan bất cứ ai có
đồng hồ lệch vài giây; đặt 2 trở lên thì nới cửa sổ tấn công mà không giải quyết
thêm vấn đề thực tế nào.

## 6. Luồng đăng nhập hai bước

```
POST /auth/login          → { "two_factor_required": true, "challenge": <JWT 5 phút> }
POST /auth/login/2fa      → hồ sơ người dùng + cookie phiên
```

- Bước hai **dùng chung bộ đếm giới hạn tốc độ** với bước một. Không có nó, kẻ
  đã có mật khẩu chỉ cần dò một triệu khả năng của 6 chữ số mà không gặp cản trở.
- Vé mang `typ = "2fa_challenge"`, và `_decode_token` từ chối mọi `typ` khác
  `"access"` — xem `docs/03-security/SESSION_LIFECYCLE.md` §3.2.
- **Fail-CLOSED:** nếu không đọc được trạng thái 2FA thì trả 503 và từ chối đăng
  nhập. Ngược lại là biến một sự cố CSDL thành cách vô hiệu hoá 2FA toàn hệ thống.
- Chấp nhận cả mã TOTP 6 chữ số lẫn mã khôi phục `xxxxx-xxxxx`. Người mất điện
  thoại mà không có đường vào nào khác thì 2FA đã biến từ lớp bảo vệ thành cách
  tự khoá mình ra ngoài.

## 7. Hạn chế đã biết

- **Không có mã QR.** Dự án không có thư viện sinh QR ở phía giao diện; bí mật
  hiện dạng nhóm 4 ký tự và mọi ứng dụng xác thực đều nhập tay được. Đây cũng là
  đường dự phòng khi máy ảnh hỏng, nên nó không hoàn toàn là thiệt.
- **Không có 2FA bắt buộc theo tổ chức.** Chủ tổ chức chưa ép được thành viên bật.
- **Không có SMS/email làm bước hai.** Cố ý: cả hai đều yếu hơn TOTP (SIM
  swapping, hộp thư bị chiếm) và tạo cảm giác an toàn sai.
- **Xoay `SECRET_KEY` làm hỏng mọi đăng ký 2FA.** Xem §2.

## 8. Kiểm chứng

```bash
# Vector RFC — 34 test, không cần CSDL
pytest tests/test_totp.py -q

# Trạng thái + chống phát lại + mã khôi phục — cần Postgres
pytest tests/test_notifications_support_2fa.py -q -k HaiBuoc
```
