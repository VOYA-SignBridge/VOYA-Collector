# Đăng nhập một lần (SSO) qua OIDC — thiết kế

*Viết 2026-08-10. **CHƯA HIỆN THỰC.** Tài liệu này tồn tại để lượt thi công không
phải thiết kế lại, và để lý do hoãn được viết ra thay vì đoán.*

---

## 1. Vì sao hoãn, nói trước

Ba lý do, xếp theo sức nặng. Đây là lý do thật, không phải lời xin lỗi:

1. **Không thể kiểm chứng được nếu không có một IdP thật.** OIDC là giao thức ba
   bên. Một bản cài đặt chỉ kiểm bằng máy chủ giả sẽ xanh trọn vẹn rồi vỡ ở lần
   đầu chạm Azure AD thật — vì phần hay hỏng nằm ở `discovery`, `nonce`, đồng hồ
   lệch, và cách IdP đó hiểu `email_verified`. Viết mã mà không kiểm được là viết
   một lời hứa, không phải một tính năng.

2. **Trường đại học chưa cấp `client_id`.** CTU dùng Microsoft 365; xin đăng ký
   ứng dụng là một quy trình hành chính, không phải một buổi ngồi code.

3. **Nó không mở khoá gì mà 2FA chưa mở.** Nhu cầu thật đằng sau "cho tôi SSO"
   thường là *"đừng bắt sinh viên nhớ thêm một mật khẩu"* và *"cho tôi tắt tài
   khoản tập trung khi sinh viên ra trường"*. Cái thứ hai mới là cái đáng giá, và
   nó cần §6 dưới đây — phần khó nhất, và cũng là phần hầu hết bản cài đặt SSO bỏ.

**Không viết "sắp có" trong quyển.** Đây là thiết kế tham chiếu, và nói đúng như
vậy thì mạnh hơn.

## 2. Luồng: Authorization Code + PKCE, KHÔNG dùng implicit

```
người dùng → GET  /auth/sso/{provider}/start
                    ├── sinh state (chống CSRF) + nonce (chống phát lại id_token)
                    ├── sinh code_verifier, lưu cùng state
                    └── 302 tới authorization_endpoint của IdP

IdP        → GET  /auth/sso/{provider}/callback?code=…&state=…
                    ├── đối chiếu state (hết hạn 10 phút, dùng MỘT lần)
                    ├── đổi code lấy token, kèm code_verifier
                    ├── xác minh id_token: chữ ký (JWKS), iss, aud, exp, nonce
                    ├── đòi email_verified = true
                    └── nối tài khoản → cấp phiên như đăng nhập thường
```

**PKCE kể cả khi có `client_secret`.** RFC 9700 khuyến nghị cho mọi loại client,
không riêng ứng dụng công khai; nó chặn kiểu tấn công chèn mã ủy quyền mà
`client_secret` một mình không chặn.

**Không dùng implicit flow.** Nó đưa token vào thanh địa chỉ, tức vào lịch sử
trình duyệt và nhật ký proxy. OAuth 2.1 đã bỏ nó.

`state` và `code_verifier` lưu ở **Redis**, TTL 10 phút, dùng một lần — chúng là
dữ liệu tạm của một luồng đang bay, không phải trạng thái của hệ thống.

## 3. Lược đồ

```sql
CREATE TABLE sso_providers (
    provider_id   TEXT PRIMARY KEY,          -- 'ctu-azure'
    tenant_id     TEXT NOT NULL,
    display_name  TEXT NOT NULL,             -- "Đăng nhập bằng tài khoản CTU"
    issuer        TEXT NOT NULL,             -- gốc để dò discovery
    client_id     TEXT NOT NULL,
    client_secret_enc TEXT NOT NULL,         -- Fernet, như user_totp.secret_enc
    -- Miền thư được phép. RỖNG nghĩa là KHÔNG cho ai — fail-closed. Xem §5.
    allowed_domains TEXT[] NOT NULL DEFAULT '{}',
    -- Tự tạo tài khoản cho người chưa có? Mặc định KHÔNG. Xem §4.
    auto_provision BOOLEAN NOT NULL DEFAULT FALSE,
    is_active     BOOLEAN NOT NULL DEFAULT TRUE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE sso_identities (
    provider_id  TEXT NOT NULL REFERENCES sso_providers(provider_id) ON DELETE CASCADE,
    -- `sub` của IdP. KHÔNG dùng email làm khoá — xem §4.
    subject      TEXT NOT NULL,
    user_id      UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    email_at_link TEXT NOT NULL,             -- thư lúc nối, để đối chiếu về sau
    linked_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at TIMESTAMPTZ,
    PRIMARY KEY (provider_id, subject)
);
CREATE UNIQUE INDEX uq_sso_identity_user ON sso_identities(provider_id, user_id);
```

`sso_providers` chịu RLS (cấu hình của một tổ chức). `sso_identities` **không** —
cùng lý do với `user_totp`: nó được đọc **trước khi biết tenant**, và RLS ở đó
fail-open. Xem `docs/TWO_FACTOR.md` §3.

## 4. Nối tài khoản — chỗ nguy hiểm nhất

**Khoá là `(provider_id, sub)`, không phải email.** `sub` là định danh bất biến
của IdP; email đổi được, và ở nhiều tổ chức nó được **tái sử dụng** — sinh viên ra
trường, hai năm sau một người khác nhận lại địa chỉ đó. Khoá theo email nghĩa là
người mới thừa hưởng tài khoản của người cũ.

Thứ tự xử lý, và **không được đảo**:

```
1. có sso_identities(provider, sub)?      → đăng nhập. Xong.
2. có users với email đó, đã xác minh?    → HỎI người dùng trước khi nối.
3. auto_provision bật và miền hợp lệ?     → tạo tài khoản mới.
4. còn lại                                → từ chối, nói rõ vì sao.
```

**Bước 2 phải hỏi, không được nối ngầm.** Nối tự động theo email là lỗ
"pre-account takeover" kinh điển: kẻ tấn công đăng ký sẵn một tài khoản mật khẩu
bằng địa chỉ của nạn nhân; khi nạn nhân sau này đăng nhập bằng SSO, hệ thống nối
danh tính thật của họ vào tài khoản kẻ tấn công đang giữ. Nối phải bắt đầu **từ
phiên đã đăng nhập của người dùng** (`POST /auth/sso/{provider}/link`), hoặc qua
một bước xác minh thư.

**`auto_provision` mặc định TẮT.** Bật nó nghĩa là bất kỳ ai có thư trong miền
được phép đều tạo được tài khoản — đúng ý ở một trường đại học, sai hoàn toàn ở
một tổ chức muốn kiểm soát ai vào.

## 5. Ba lượt kiểm bắt buộc

Bỏ bất kỳ cái nào cũng biến SSO thành cửa mở:

| Kiểm | Bỏ thì sao |
|---|---|
| `id_token` ký bởi JWKS của đúng `issuer`, `aud == client_id` | nhận token của ứng dụng khác cùng IdP |
| `nonce` khớp giá trị đã sinh ở bước `start` | phát lại một `id_token` bắt được trước đó |
| `email_verified == true` **và** miền nằm trong `allowed_domains` | IdP cho người dùng tự khai email → mạo danh bất kỳ ai |

`allowed_domains` rỗng = **từ chối tất cả**, không phải cho phép tất cả. Một mảng
rỗng đọc như "chưa cấu hình", và hướng hỏng đúng của "chưa cấu hình" là đóng.

## 6. Phần khó, và là phần đáng giá nhất: huỷ kích hoạt

Đây là lý do thật để một trường muốn SSO, và cũng là phần hầu hết bản cài đặt bỏ:
**OIDC không nói cho bạn biết khi một tài khoản bị vô hiệu hoá ở phía IdP.**

Sinh viên ra trường, tài khoản Azure bị tắt — nhưng phiên trên hệ thống này vẫn
sống, và refresh token vẫn xoay được 90 phút một lần vô hạn.

Ba mức, chọn theo mức độ nghiêm túc:

1. **Rẻ:** rút ngắn `refresh_token_expire_minutes` cho tài khoản SSO, buộc quay
   lại IdP thường xuyên. Thô, nhưng đúng hướng và làm được ngay.
2. **Đúng:** hỗ trợ **OIDC Back-Channel Logout** — IdP gọi
   `POST /auth/sso/{provider}/backchannel-logout` với một `logout_token`. Nối vào
   `activity.force_logout_user()` đã có sẵn.
3. **Đầy đủ:** thêm SCIM để IdP đẩy cả vòng đời tài khoản. Đắt, và chỉ đáng khi
   có nhiều tổ chức thật.

Khuyến nghị: (1) ngay từ lượt đầu, (2) khi có tổ chức thật yêu cầu.

## 7. Kế hoạch test cho lượt thi công

| Phải chứng minh | Cách |
|---|---|
| `state` sai / hết hạn / dùng lại → từ chối | ba trường hợp riêng, kỳ vọng 401 |
| `nonce` không khớp → từ chối | dựng `id_token` hợp lệ nhưng sai nonce |
| `aud` của ứng dụng khác → từ chối | ký bằng cùng JWKS, đổi `aud` |
| `email_verified = false` → từ chối | ghim, vì đây là lỗ mạo danh |
| miền ngoài `allowed_domains` → từ chối | và `allowed_domains` rỗng cũng từ chối |
| KHÔNG nối ngầm vào tài khoản mật khẩu cùng email | ghim hướng "pre-account takeover" |
| `auto_provision` tắt → người lạ bị từ chối, không được tạo tài khoản | |
| đăng nhập lại dùng lại đúng `sso_identities`, không đẻ hàng mới | |
| tenant A không thấy `sso_providers` của tenant B | hai tenant, đọc chéo, kỳ vọng 0 dòng |

JWKS và `token_endpoint` dựng bằng máy chủ giả cục bộ; **nhưng** phải có ít nhất
một lượt chạy tay với IdP thật trước khi bật cho người dùng — xem §1.

## 8. Thứ tự đúng

**Xong 2FA trước** (đã xong 2026-08-10) → xin `client_id` từ CTU → hiện thực §2–§5
→ chạy tay với Azure AD thật → §6 mức (1) → bật cho một nhóm nhỏ → §6 mức (2).
