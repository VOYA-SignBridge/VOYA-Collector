# Vòng đời phiên đăng nhập

*Vá 2026-08-10. Rà soát gốc: `docs/03-security/AUTH_TOKEN_LIFECYCLE.md` (2026-07-31).*

Năm mục của bản rà soát đều đã đóng. Tài liệu này ghi **cơ chế sau khi vá**, các
đánh đổi đã chọn, và **năm lỗi tìm được trong lúc vá** — vì bốn trong năm nghiêm
trọng hơn chính những lỗi đang được sửa.

---

## 1. Cơ chế

| Thành phần | Kiểu | Sống bao lâu | Lưu ở đâu |
|---|---|---|---|
| access | JWT HS256, có `jti` + `fam` | 60 phút | không lưu server |
| refresh | chuỗi đục 48 byte | 90 phút kể từ lần xoay gần nhất | `refresh_tokens`, chỉ giữ SHA-256 |
| vé bước hai | JWT, `typ = 2fa_challenge` | 5 phút | không lưu |

**Họ token** (`family_id`): một lần đăng nhập = một họ. Refresh token và access
token của cùng phiên mang chung giá trị này. Xoay token giữ nguyên họ.

Nhờ đó có hai mức thu hồi khác nhau, và **chúng không được lẫn vào nhau**:

| Việc | Phạm vi | Cơ chế |
|---|---|---|
| Đăng xuất | đúng MỘT phiên | chặn `jti` trong Redis |
| Phát hiện token bị dùng lại | đúng MỘT họ | chặn `fam` + `reuse_detected_at` |
| Đổi mật khẩu / quản trị thu hồi | MỌI thiết bị | `users.sessions_invalid_before` |

Nhầm ba mức này là cách một bản vá biến thành hồi quy: dùng `force_logout_user`
cho nút "Đăng xuất" sẽ làm người đăng xuất trên điện thoại văng khỏi máy tính.

## 2. Phát hiện tái sử dụng, và cái giá của nó

Xoay token mà không phát hiện tái sử dụng thì kết quả **bị lộn ngược**:

```
t0  kẻ trộm lấy được refresh cookie
t1  kẻ trộm gọi /refresh trước  → token cũ revoke, kẻ trộm cầm token MỚI
t2  người dùng thật gọi /refresh → token của họ đã revoke → 401 → ĐĂNG XUẤT
t3  kẻ trộm tiếp tục xoay bình thường, không ai biết
```

Nạn nhân bị đá ra, kẻ trộm ở lại. RFC 9700 §4.14.2 đòi thu hồi cả họ.

**Cửa sổ ân hạn 15 giây** (`REFRESH_GRACE_SECONDS`) là chỗ hai yêu cầu kéo ngược
chiều nhau. Phát hiện tái sử dụng muốn ân hạn bằng 0; nhưng hai tab cùng mở sẽ
đua nhau gọi `/refresh` một cách hoàn toàn hợp lệ, và vì cookie dùng chung cho cả
trình duyệt nên tab thua kéo theo **cả hai** tab cùng văng.

Cái giá, nói thẳng: **kẻ trộm dùng token trong vòng 15 giây kể từ lần xoay hợp lệ
vẫn lọt.** 15 giây đủ dài cho một cuộc đua giữa các tab (chúng cách nhau
mili-giây) và quá ngắn để làm nền cho tấn công thật.

Một chi tiết nhỏ nhưng quyết định: câu SQL ghi `COALESCE(revoked_at, NOW())` chứ
không phải `NOW()`. Nếu mỗi lượt đua ghi đè mốc thu hồi, cửa sổ ân hạn **trượt về
phía trước mỗi lần token được dùng lại**, và một token bị đánh cắp sống vĩnh viễn
chỉ bằng cách gọi lại đều đặn 10 giây một lần. Ghim ở
`test_moc_thu_hoi_KHONG_truot_theo_moi_lan_dua`.

## 3. Năm lỗi tìm được TRONG lúc vá

Bốn trong năm do test bắt; cái còn lại (§3.3) do tự soát lại — và đó chính là
lý do nó được ghim bằng ba test khác nhau ngay sau khi phát hiện.

### 3.1 Bế tắc CSDL — nghiêm trọng nhất

Bản đầu gọi `activity.force_logout_user()` từ bên trong `_burn_token_family`, mà
hàm đó chạy **bên trong giao dịch đang giữ khoá** trên đúng những dòng
`refresh_tokens` nó muốn sửa. `force_logout_user` mở một kết nối Postgres **thứ
hai**; kết nối đó chờ khoá của kết nối thứ nhất, kết nối thứ nhất chờ hàm trả về.
Treo vĩnh viễn — và nó sẽ treo trên máy chủ thật, mỗi lần phát hiện tái sử dụng.

Sửa: chặn theo họ trong Redis, không mở kết nối nào. Ghim ở
`test_phat_hien_tai_su_dung_KHONG_TREO` (có trần thời gian 5 giây).

### 3.2 Vé bước hai dùng thay access token được

Mọi token đều ký bằng **cùng một khoá**, nên chữ ký hợp lệ chỉ chứng minh "hệ
thống này phát ra nó" — không chứng minh nó được phát ra **để làm gì**.
`_decode_token` lúc đầu chỉ kiểm `sub`, nên vé bước hai đi thẳng qua cửa xác
thực: người vừa nhập đúng mật khẩu vào được hệ thống mà **chưa qua bước hai**.

Sửa: `_decode_token` từ chối mọi `typ` khác `"access"`. Token cấp trước bản vá
không mang `typ` và vẫn được nhận — đường chuyển tiếp tự đóng sau 60 phút.

### 3.3 Bỏ `response_model` làm rò băm mật khẩu

Endpoint `/auth/login` phải trả **hai** hình dạng — hồ sơ người dùng, hoặc vé
bước hai — nên `response_model=UserOut` bị bỏ. Nhưng `UserOut` là **danh sách cho
phép**, và nó là thứ *duy nhất* ngăn `password_hash` đi ra: `auth._row_to_user`
mang cột đó theo trên mọi hồ sơ, cố ý, vì `authenticate_user` cần nó.

Kết quả: băm bcrypt đi ra theo **mọi lượt đăng nhập thành công**.

Lỗi sống vài phút và do tự soát lại mà thấy, **không phải do test bắt** — đó là
lý do giờ có ba test: một cho hàm lọc, một gửi yêu cầu HTTP thật rồi đọc thân
phản hồi, và một canh chung buộc mọi đường không khai `response_model` phải có
lý do viết ra (`test_login_response_shape.py`).

Bài học chung: **bỏ `response_model` là gỡ một bộ lọc bảo mật**, không phải một
chi tiết về tài liệu API.

### 3.4 Mốc thu hồi ghi hụt trong im lặng

`_persist_force_logout_marker` mở kết nối **không có scope**, và `users` có
row-level security. Câu `UPDATE` không bị từ chối — nó khớp **0 dòng**. Lệnh thu
hồi phiên của quản trị viên trông như thành công mà không thu hồi gì.

Sửa: `system_scope` + `apply_scope`, cộng một dòng `ERROR` khi `rowcount == 0`.
`activity.py` được thêm vào danh sách vượt ranh giới ở `test_tenant_isolation`.

### 3.5 Thêm một truy vấn vào đường đăng nhập, và cho nó fail-CLOSED

Bản đầu gọi `two_factor.is_enabled()` ngay trong `login`, bọc `try/except` rồi
trả 503 nếu hỏng. Ý định đúng — không đọc được trạng thái 2FA thì không được cho
qua — nhưng hệ quả sai: một trục trặc thoáng qua của cơ sở dữ liệu biến thành
**"không ai đăng nhập được"**, và nó đã làm một test hỏng ở bước dựng trong lượt
chạy toàn bộ.

Sửa: `LEFT JOIN user_totp` vào chính truy vấn `_fetch_user_by_login` vốn đã chạy.
**Không truy vấn thêm, không chỗ hỏng thêm** — cùng cách `sessions_invalid_before`
đi ké `_fetch_user_by_id`.

Bài học chung: *fail-closed* chỉ đúng khi thứ có thể hỏng là một **quyết định về
quyền**. Nếu thứ hỏng là một **lượt đọc phụ**, câu trả lời không phải là chọn
hướng hỏng — mà là bỏ lượt đọc đó đi.

## 4. Hai chỗ fail-open có chủ ý

Không phải sơ suất, nên ghi ra để lần sau không ai "sửa" nhầm:

- **`is_access_token_denied` trả `False` khi Redis chết.** Nó chỉ nới cho token
  đã đăng xuất sống nốt tối đa 60 phút — đúng bằng hành vi *trước* bản vá, không
  mở thêm gì mới.
- **Mốc thu hồi bền đọc từ `users.sessions_invalid_before`, đi ké truy vấn
  `_fetch_user_by_id`** vốn đã chạy mỗi request. Bản đầu cho `is_user_denied` mở
  kết nối Postgres riêng mỗi lần — đổi một lỗ bảo mật lấy một nút thắt cổ chai.

## 5. Dọn bảng

`refresh_tokens` chỉ lớn lên: một dòng mỗi lần đăng nhập **và** mỗi lần xoay
(~1 dòng/giờ cho mỗi người đang hoạt động; ~290 nghìn dòng/năm với 100 người).

Beat `cleanup-refresh-tokens-daily` xoá token hết hạn **quá 7 ngày**. Giữ lại 7
ngày chứ không xoá ngay vì chuỗi `replaced_by` là thứ duy nhất dựng lại được
đường xoay token khi điều tra một vụ tái sử dụng.

## 6. Kiểm chứng

Chạy trên Postgres thật, không giả lập — thứ đang được kiểm phần lớn là các câu
SQL, và một bản giả sẽ chỉ kiểm lại chính bản giả đó.

| Tệp | Số test | Canh gì |
|---|---|---|
| `test_session_lifecycle.py` | 27 | xoay token, ân hạn, đốt họ, denylist, mốc bền, dọn bảng, không rò băm |
| `test_login_response_shape.py` | 3 | hình dạng phản hồi ở tầng HTTP + cổng canh `response_model` |

```bash
docker run ... voya_backend_test:latest python -m pytest \
  tests/test_session_lifecycle.py tests/test_login_response_shape.py -q
```
