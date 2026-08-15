# Vòng đời phiên đăng nhập — bốn việc cần sửa

Rà soát ngày 2026-07-31, trong lúc merge `feature/vocab-schema-v2` vào
`deploy_ctu_ver-2.2.1`.

**Không việc nào dưới đây do merge gây ra** — cả hai nhánh đều có. Chúng cũng
không nằm trong phạm vi merge: đều đụng `backend/app/auth.py` và schema bảng
`refresh_tokens`, nên nên làm thành một thay đổi riêng, có test riêng.

---

## 0. Hiện trạng

### Cơ chế

| Thành phần | Kiểu | Sống bao lâu | Lưu ở đâu |
|---|---|---|---|
| access | JWT (HS256), stateless | `ACCESS_TOKEN_EXPIRE_MINUTES` = **60 phút** | không lưu server |
| refresh | chuỗi ngẫu nhiên 48 byte, đục | `REFRESH_TOKEN_EXPIRE_MINUTES` = **90 phút** kể từ lần xoay gần nhất | `refresh_tokens`, chỉ giữ SHA-256 |
| csrf | ngẫu nhiên, double-submit | theo access | cookie đọc được (cố ý) |

Cả ba đi bằng cookie `httpOnly` (trừ csrf), nên XSS không đọc được token.

### Luồng

```
POST /auth/login
    ├── authenticate_user()  (bcrypt, có dummy-hash chống dò tên)
    ├── check_login_allowed() / reset_login_attempts()   ← throttle, xem OBSERVABILITY_PLAN §7
    ├── activity.get_user_lock()  → 403 nếu bị admin khoá
    └── set_auth_cookies(access, refresh=create_refresh_token(), csrf)

POST /auth/refresh
    └── rotate_refresh_token(cookie)
            ├── không tìm thấy / hết hạn / đã revoke / user inactive → None → 401 + xoá cookie
            └── hợp lệ → UPDATE revoked_at = NOW() cho cái cũ
                         INSERT cái mới
                         → access mới + csrf mới

POST /auth/logout
    └── revoke_refresh_token(cookie) + clear_auth_cookies()

POST /auth/reset-password
    └── đổi mật khẩu + đánh dấu mọi reset-token đã dùng
        + UPDATE refresh_tokens SET revoked_at = NOW() WHERE user_id = ...   (cùng transaction)

admin khoá user  →  activity.lock_user()
    └── đặt mốc force-logout (Redis) + _revoke_all_refresh_tokens()
        → get_current_user_optional() từ chối mọi access token có iat < mốc
```

### Schema hiện tại

```sql
CREATE TABLE refresh_tokens (
    token_hash TEXT PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    expires_at TIMESTAMPTZ NOT NULL,
    revoked_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_refresh_tokens_user_id ON refresh_tokens(user_id);
```

### Những chỗ ĐANG ĐÚNG, đừng đụng vào

- Refresh token là chuỗi đục, DB chỉ giữ SHA-256 → lộ DB không cho ai đăng nhập được.
- Xoay token mỗi lần dùng (rotation) — đúng hướng, chỉ thiếu vế phát hiện tái sử dụng (§1).
- `authenticate_user` verify một hash giả khi không có user → chặn dò tên qua thời gian phản hồi.
- Admin khoá user thì cắt luôn phiên đang mở, không chỉ chặn ở màn đăng nhập.
- `refresh_token_expire_minutes = 90` là **trần phiên nhàn rỗi có chủ ý**, khớp với
  inactivity logout phía client. Không phải "quá khắt khe" — giữ nguyên.

---

## 1. Xoay token không phát hiện tái sử dụng

**Mức độ: cao (bảo mật).**

### Hiện tượng

`rotate_refresh_token` gặp token đã `revoked_at IS NOT NULL` thì chỉ `return None`
→ 401 → xoá cookie. Không có phản ứng nào khác.

### Vì sao sai

Xoay token chỉ có giá trị khi đi kèm **phát hiện tái sử dụng**. Một token đã bị
revoke mà quay lại đúng là dấu hiệu nó đã bị sao chép — OAuth 2.0 Security BCP
(RFC 9700) yêu cầu thu hồi cả họ token khi gặp trường hợp này. Thiếu vế đó, kết
quả bị lộn ngược:

```
t0  kẻ trộm lấy được refresh cookie (log, proxy, extension, máy dùng chung)
t1  kẻ trộm gọi /refresh trước  → token cũ revoke, kẻ trộm cầm token MỚI hợp lệ
t2  người dùng thật gọi /refresh → token của họ đã bị revoke → 401 → ĐĂNG XUẤT
t3  kẻ trộm tiếp tục xoay token bình thường, không ai biết
```

Nạn nhân bị đá ra, kẻ trộm ở lại, và **không có cảnh báo nào** được ghi.

### Cách sửa

Thêm khái niệm **họ token** (một lần đăng nhập = một họ) và con trỏ tới token kế
nhiệm:

```sql
ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS family_id UUID;
ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS replaced_by TEXT;
ALTER TABLE refresh_tokens ADD COLUMN IF NOT EXISTS reuse_detected_at TIMESTAMPTZ;
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_family  ON refresh_tokens(family_id);
CREATE INDEX IF NOT EXISTS idx_refresh_tokens_expires ON refresh_tokens(expires_at);
```

`create_refresh_token` sinh `family_id` mới; `rotate_refresh_token` giữ nguyên
`family_id` của token cha và ghi `replaced_by`.

Thuật toán mới (gộp luôn bản vá §2):

```
row ← SELECT * FROM refresh_tokens WHERE token_hash = $1
nếu không có row              → None            (chưa bao giờ tồn tại)
nếu row.expires_at < now      → None
nếu row.reuse_detected_at     → None            (họ này đã bị đốt)

nếu row.revoked_at IS NULL:                     ← đường bình thường
    cấp token mới cùng family_id
    UPDATE row SET revoked_at = NOW(), replaced_by = <hash mới>
    trả về token mới

# tới đây: token đã bị revoke rồi mà vẫn quay lại
nếu now - row.revoked_at <= GRACE_SECONDS:      ← cuộc đua nhiều tab, §2
    cấp token mới cùng family_id, trả về
ngược lại:                                       ← coi là bị đánh cắp
    UPDATE refresh_tokens SET revoked_at = NOW() WHERE family_id = row.family_id
    UPDATE row SET reuse_detected_at = NOW()
    activity.force_logout_user(row.user_id, reason="phát hiện tái sử dụng refresh token")
    log ERROR: auth.refresh_reuse_detected
    trả None
```

`GRACE_SECONDS` đề xuất **15 giây** (`REFRESH_GRACE_SECONDS`).

### Đánh đổi phải biết

Trong cửa sổ ân hạn, một token cha có thể sinh ra nhiều token con — nghĩa là kẻ
trộm dùng token trong vòng 15 giây kể từ lần xoay hợp lệ vẫn qua được. Đây là
cái giá phải trả để §2 không đá người dùng thật ra ngoài. 15 giây là khoảng đủ
cho một cuộc đua giữa các tab và quá ngắn để làm nền cho tấn công thực tế.

Nếu muốn siết thêm: đếm số con sinh ra trong một cửa sổ ân hạn, quá 3 thì cũng
coi là bất thường.

> **Không thể** trả lại đúng token kế nhiệm cho tab thua, vì DB chỉ giữ hash chứ
> không giữ token thô. Đó là lý do cách xử lý ân hạn là *cấp token mới*, không
> phải *trả lại token cũ*.

---

## 2. Nhiều tab → đăng xuất oan

**Mức độ: cao (người dùng gặp hằng ngày).**

### Hiện tượng

Frontend đã có single-flight refresh — `refreshPromise` trong
`frontend/src/api/axiosClient.ts` (~dòng 146) gom mọi request 401 vào **một** lần
gọi `/auth/refresh`. Nhưng biến đó nằm trong bộ nhớ của **một tab**.

Hai tab cùng mở, access token hết hạn:

```
tab A: /refresh → xoay thành công → cookie = token2
tab B: /refresh → gửi token1 (đã revoke ở trên) → 401 → clear_auth_cookies()
                                                        ↑
                            cookie dùng chung cho cả trình duyệt
                            → CẢ HAI TAB bị đăng xuất
```

Trang được mở lại (F5) giữa lúc refresh đang bay cũng cho kết quả tương tự.

### Cách sửa

Cửa sổ ân hạn ở §1 xử lý trọn vẹn trường hợp này — token vừa bị revoke trong 15
giây được cấp token mới thay vì bị từ chối. Không cần đổi frontend.

Nếu muốn chắc hơn ở phía client: đồng bộ giữa các tab bằng `BroadcastChannel`
hoặc một khoá trong `localStorage`, để chỉ một tab thực sự gọi `/refresh`. Là
tối ưu thêm, **không** thay thế được bản vá phía server (một trình duyệt khác,
hoặc app di động, vẫn đua như thường).

---

## 3. Đăng xuất và đổi mật khẩu không giết access token

**Mức độ: trung bình–cao (bảo mật).**

### Hiện tượng

Access token là JWT stateless. `logout` chỉ revoke refresh token và xoá cookie
khỏi trình duyệt — **không** có danh sách chặn nào cho access token. Nếu token đã
bị chụp lại ở đâu đó (log, proxy, extension, máy dùng chung), nó **vẫn dùng được
tới 60 phút** sau khi người dùng bấm đăng xuất.

Reset mật khẩu cũng vậy. Ta đã giữ bản deploy revoke *toàn bộ* refresh token —
đúng và cần thiết — nhưng access token đang sống thì vẫn chạy hết 60 phút. Với
thao tác mà lý do thường là "tôi nghi tài khoản bị chiếm", 60 phút là quá dài.

### Cách sửa — hai trường hợp KHÁC NHAU, đừng dùng chung một búa

Máy móc sẵn có là `activity.force_logout_user(user_id)`: nó đặt một mốc thời gian
và `get_current_user_optional` từ chối mọi token có `iat` nhỏ hơn mốc đó.

**Reset mật khẩu → dùng `force_logout_user` là đúng.** Ở đây "đá mọi thiết bị" là
hành vi mong muốn.

**Logout thì KHÔNG.** `force_logout_user` đá toàn bộ thiết bị của user: đăng xuất
trên điện thoại sẽ làm văng luôn phiên trên máy tính. Đó là hồi quy, không phải
bản vá.

Logout cần chặn **đúng phiên hiện tại**:

1. Thêm `jti` (id ngẫu nhiên) và `fam` (family_id ở §1) vào claim của access token.
2. Logout đưa `jti` (hoặc cả `fam`) vào denylist Redis, TTL = thời gian còn lại
   của token — tự hết hạn, không cần dọn.
3. `get_current_user_optional` kiểm denylist đó.

Chi phí gần như bằng không: hàm này **đã** gọi Redis mỗi request qua
`activity.is_user_denied`, nên gộp thêm một lần kiểm là xong.

---

## 4. Bảng `refresh_tokens` chỉ lớn lên

**Mức độ: thấp (vận hành).**

Mỗi lần đăng nhập và **mỗi lần xoay** đều `INSERT` một dòng; không có gì xoá —
`revoked_at` chỉ là đánh dấu. Access sống 60 phút nên một người dùng hoạt động
sinh khoảng một dòng mỗi giờ, cộng một dòng mỗi lần đăng nhập. Khoảng 100 người
dùng × 8 giờ/ngày ≈ 800 dòng/ngày, ~290k dòng/năm. Không chết ngay, nhưng không
có lý do gì để giữ.

Thêm một beat vào `backend/app/worker.py` (đã có sẵn hạ tầng beat):

```sql
DELETE FROM refresh_tokens
WHERE expires_at < NOW() - INTERVAL '7 days';
```

Chạy mỗi ngày. Giữ lại 7 ngày để còn điều tra được khi có sự cố. Cần index trên
`expires_at` (đã kèm trong migration ở §1).

---

## 5. Một chỗ QUÁ LỎNG: force-logout im lặng chết khi Redis sập

Trong `get_current_user_optional`, phần kiểm force-logout nằm trong
`try / except Exception: pass`, và `activity.is_user_denied` cũng trả `False` khi
không lấy được Redis client. Nghĩa là **Redis chết thì mọi lệnh force-logout của
admin ngừng có tác dụng**: người vừa bị đá ra vẫn dùng app bình thường, và không
có dòng log nào cho biết cơ chế đang mù.

Với rate limit thì fail-open là lựa chọn đúng (khoá cả nhà vì Redis nấc còn tệ
hơn — xem `rate_limit.py`). Với **thu hồi phiên** thì không hiển nhiên như vậy.

Ba mức, chọn theo khẩu vị rủi ro:

1. **Rẻ nhất:** log `ERROR` khi không kiểm được, cộng một metric. Hành vi giữ
   nguyên, nhưng thôi mù.
2. **Đúng nhất:** đưa mốc force-logout xuống Postgres
   (`users.sessions_invalid_before TIMESTAMPTZ`), Redis chỉ còn là cache. Redis
   chết thì rơi về Postgres, không mất hiệu lực.
3. Fail-closed hoàn toàn — **không khuyến nghị**: Redis nấc một cái là cả hệ
   thống 401.

Đề nghị làm (2), vì nó cũng giải luôn bài toán "mốc force-logout biến mất khi
Redis restart" mà hiện tại không ai để ý.

---

## 6. Thứ tự triển khai đề nghị

| Bước | Việc | Vì sao trước/sau |
|---|---|---|
| 1 | Migration §1 (3 cột + 2 index) | Mọi thứ khác dựa lên nó; `ADD COLUMN IF NOT EXISTS` nên an toàn với dữ liệu đang chạy |
| 2 | §1 + §2 cùng một lần | Hai bản vá **kéo ngược chiều nhau** — ân hạn nới đúng cái mà reuse detection siết. Làm riêng lẻ sẽ hoặc đá oan người dùng, hoặc mở cửa cho token bị trộm |
| 3 | §4 beat dọn bảng | Độc lập, rẻ, làm lúc nào cũng được |
| 4 | §3 denylist `jti` cho logout | Cần thêm claim vào access token → token cũ chưa có `jti`, phải chịu được cả hai dạng trong thời gian chuyển tiếp |
| 5 | §5 mức (2) — mốc force-logout xuống Postgres | Đụng `activity.py` + schema `users`, tách riêng cho dễ review |

### Kiểm chứng

Những tính chất sau nên có test, chạy được với Redis + Postgres thật (xem
`backend/tests/test_login_rate_limit.py` để lấy mẫu cách dựng):

- token hợp lệ → xoay được, token cũ chết
- token đã revoke **trong** cửa sổ ân hạn → vẫn cấp được token mới (mô phỏng hai tab)
- token đã revoke **ngoài** cửa sổ ân hạn → cả họ bị thu hồi + có log + user bị force-logout
- logout → access token của **chính phiên đó** hết tác dụng ngay, phiên trên thiết bị khác **vẫn sống**
- reset mật khẩu → **mọi** phiên chết ngay, không đợi hết 60 phút
- beat dọn bảng không xoá nhầm token còn hạn

---

## Phụ lục: chỗ code liên quan

| Việc | File |
|---|---|
| Cấp / xoay / thu hồi refresh token | `backend/app/auth.py` (`create_refresh_token`, `rotate_refresh_token`, `revoke_refresh_token`) |
| Đọc token từ cookie/Bearer, kiểm force-logout | `backend/app/auth.py` (`get_current_user_optional`) |
| Endpoint login / refresh / logout / reset | `backend/app/routers/auth.py` |
| Đặt & xoá cookie, path theo sub-path deploy | `backend/app/cookie_auth.py` |
| Mốc force-logout, khoá user | `backend/app/activity.py` |
| Schema `refresh_tokens` | `backend/app/storage/metadata_db.py` (~dòng 285) |
| Single-flight refresh phía client | `frontend/src/api/axiosClient.ts` (~dòng 146) |
