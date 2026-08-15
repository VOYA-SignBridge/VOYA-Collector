from __future__ import annotations

import hashlib
import logging
import secrets
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional, Tuple
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.cookie_auth import ACCESS_COOKIE
from app.storage.postgres_connection import connect_postgres
from app.tenancy import DEFAULT_TENANT_ID

logger = logging.getLogger(__name__)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

# Precomputed bcrypt hash used to equalize login response time when the account
# does not exist. Without it, a missing user returns immediately (no bcrypt)
# while a real user with a wrong password pays the bcrypt cost — an attacker can
# measure that gap to enumerate valid usernames. Verifying against this dummy on
# the "no such user" path makes both branches take the same time.
_DUMMY_PASSWORD_HASH = pwd_context.hash("voya-timing-equalizer-not-a-real-secret")


def _get_conn():
    return connect_postgres(connect_timeout=5)


@contextmanager
def _identity_cursor(*, dict_rows: bool = True):
    """A cursor for the IDENTITY plane, which runs outside every tenant.

    Why this whole module is exempt from row-level security
    -------------------------------------------------------
    `users` carries a tenant policy (see `storage/rls.py`), and authentication
    cannot obey it. The order of events makes that unavoidable:

        request arrives -> decode token -> read users.tenant_id -> SET scope

    The read that DECIDES the scope cannot itself be filtered by that scope: a
    policy applied there evaluates against an unset GUC, matches nothing, and
    nobody can log in. The same holds for a login by email (there is no session
    yet) and for a password reset (the token names a row, not a tenant).

    So every statement in this module runs in system scope - deliberately, and
    in one place rather than eight. The reason string is what makes it
    auditable, and `test_tenant_isolation.py` lists this file on the boundary
    allowlist so a ninth call site cannot appear unnoticed.

    `apply_scope` is still called. Without it the GUCs keep whatever the
    previous holder of this connection left behind; these are unpooled
    connections today, but relying on that is the kind of assumption that stops
    being true after an unrelated refactor.
    """
    from app.storage.rls import apply_scope
    from app.tenant_context import system_scope

    factory = RealDictCursor if dict_rows else None
    with system_scope("auth: identity plane, runs before a tenant is known"):
        conn = _get_conn()
        try:
            with conn:
                with conn.cursor(cursor_factory=factory) as cur:
                    apply_scope(cur)
                    yield cur
        finally:
            conn.close()


def _normalize_login(identifier: str) -> str:
    return (identifier or "").strip().lower()


def _row_to_user(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not row:
        return None
    return {
        "id": str(row["id"]),
        "username": row["username"] or "",
        "email": row["email"] or "",
        "password_hash": row["password_hash"] or "",
        "is_active": bool(row.get("is_active", True)),
        "is_admin": bool(row.get("is_admin", False)),
        "created_at": row.get("created_at"),
        # Carried on the user dict so a handler that already has the caller
        # does not need a second query to learn which tenant they belong to.
        # The request SCOPE still comes from the middleware, never from this
        # field - this is for display and authorisation checks, not scoping.
        "tenant_id": (row.get("tenant_id") or DEFAULT_TENANT_ID),
        # NULL until the person proves they receive mail at that address. Only
        # consulted when REQUIRE_EMAIL_VERIFICATION is on — see `login`.
        "email_verified_at": row.get("email_verified_at"),
        # Mốc thu hồi phiên BỀN. Đi ké truy vấn này chứ không tự hỏi riêng: hàm
        # gọi nó chạy trên mọi request, nên một truy vấn thêm ở đây là một
        # truy vấn thêm cho toàn hệ thống.
        "sessions_invalid_before": row.get("sessions_invalid_before"),
        # Chỉ có mặt trên đường ĐĂNG NHẬP (`_fetch_user_by_login` LEFT JOIN nó).
        # `None` nghĩa là "chưa hỏi", KHÁC với `False` nghĩa là "đã hỏi, chưa
        # bật" — và `login` phân biệt hai cái đó thay vì đoán.
        "two_factor_enabled": row.get("two_factor_enabled"),
    }


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False


def create_access_token(
    data: Dict[str, Any],
    expires_delta: Optional[timedelta] = None,
) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    payload.update(
        {
            "exp": expire,
            "iat": datetime.now(timezone.utc),
            "typ": "access",
            # `jti` là thứ cho phép ĐĂNG XUẤT giết được đúng phiên này.
            #
            # Access token là JWT không trạng thái, nên trước đây bấm "Đăng xuất"
            # chỉ xoá cookie khỏi trình duyệt — token đã bị chụp lại ở đâu đó
            # vẫn dùng được hết 60 phút. Có `jti` thì đăng xuất bỏ được đúng một
            # định danh vào danh sách chặn.
            #
            # Vì sao KHÔNG dùng `force_logout_user` cho đăng xuất: hàm đó đá mọi
            # thiết bị của người dùng, nên đăng xuất trên điện thoại sẽ làm văng
            # phiên trên máy tính. Đó là hồi quy, không phải bản vá.
            "jti": uuid.uuid4().hex,
        }
    )
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def _decode_token(token: str) -> Dict[str, Any]:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_aud": False},
        )
    except JWTError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        ) from exc

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing subject",
        )

    # Token nào cũng ký bằng CÙNG một khoá, nên chữ ký hợp lệ chỉ chứng minh
    # "hệ thống này phát ra nó" — không chứng minh nó được phát ra để làm gì.
    #
    # Cụ thể: vé hai bước (`typ = 2fa_challenge`) cũng ký bằng khoá đó. Không có
    # dòng dưới đây, người vừa nhập đúng mật khẩu có thể lấy vé đó dùng thay
    # access token và vào thẳng hệ thống — tức là bước hai tự vô hiệu hoá chính
    # nó. Phát hiện khi viết test cho luồng 2FA.
    #
    # Token cấp TRƯỚC khi có claim này không mang `typ`; chúng vẫn được chấp
    # nhận để lần triển khai không 401 hàng loạt. Đường chuyển tiếp đó tự đóng
    # sau một vòng đời access token.
    typ = payload.get("typ")
    if typ is not None and typ != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Loại token không dùng được cho thao tác này",
        )
    return payload


def _subject_of(token: str) -> Optional[str]:
    """`sub` of a token that is valid RIGHT NOW, else None. Never raises.

    An expired or forged token is simply "no subject" — which is what keeps the
    stale-Bearer migration path harmless in get_current_user_optional().
    """
    try:
        return str(_decode_token(token).get("sub") or "") or None
    except Exception:
        return None


def get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode a raw JWT and fetch the user, returning None instead of raising.

    Intended for WebSocket endpoints, where the token arrives as a query
    param (browsers cannot set Authorization headers on WS connections)
    rather than through the HTTPBearer dependency used by regular routes.
    """
    try:
        payload = _decode_token(token)
    except HTTPException:
        return None
    user = _fetch_user_by_id(str(payload.get("sub") or ""))
    if not user or not user.get("is_active", True):
        return None
    return user


def _fetch_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    with _identity_cursor() as cur:
        cur.execute(
            """
            SELECT id, username, email, password_hash, is_active, is_admin,
                   created_at, tenant_id, email_verified_at,
                   sessions_invalid_before
            FROM users
            WHERE id = %s
            """,
            (user_id,),
        )
        row = cur.fetchone()
        return _row_to_user(row)


def _fetch_user_by_login(identifier: str) -> Optional[Dict[str, Any]]:
    login = _normalize_login(identifier)
    if not login:
        return None

    with _identity_cursor() as cur:
        cur.execute(
            """
            SELECT u.id, u.username, u.email, u.password_hash, u.is_active,
                   u.is_admin, u.created_at, u.tenant_id, u.email_verified_at,
                   u.sessions_invalid_before,
                   -- 2FA đi KÈM truy vấn này chứ không hỏi riêng.
                   --
                   -- Bản đầu gọi `two_factor.is_enabled()` trong `login`, tức
                   -- thêm một truy vấn vào đường nóng VÀ thêm một chỗ hỏng: lượt
                   -- kiểm đó fail-CLOSED (503), nên một trục trặc thoáng qua của
                   -- CSDL biến thành "không ai đăng nhập được". LEFT JOIN cho ra
                   -- cùng câu trả lời với 0 truy vấn thêm và 0 chỗ hỏng thêm.
                   (t.confirmed_at IS NOT NULL) AS two_factor_enabled
            FROM users u
            LEFT JOIN user_totp t ON t.user_id = u.id
            WHERE lower(u.username) = %s OR lower(u.email) = %s
            LIMIT 1
            """,
            (login, login),
        )
        row = cur.fetchone()
        return _row_to_user(row)


def create_user(
    username: str,
    email: str,
    password: str,
    is_admin: bool = False,
    tenant_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an account in a tenant.

    `tenant_id=None` means the bootstrap tenant, and that is a *policy*, not a
    fallback: an open registration with no invitation joins the public tenant,
    which is where the pre-tenant corpus lives. Spelled out here rather than
    left to the column default so the choice is visible at the call site, and so
    changing that default later cannot silently move new accounts.

    A caller-supplied id is validated against the strict alphabet before it
    reaches SQL. This value ends up naming a storage directory (A4), so an
    unchecked one is a path, not just a string.
    """
    from app.tenancy import normalize_tenant_id

    tenant = normalize_tenant_id(tenant_id)
    username_norm = (username or "").strip()
    email_norm = _normalize_login(email)
    if not username_norm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is required")
    if not email_norm:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email is required")
    if len(password or "") < int(settings.min_password_length):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.min_password_length} characters",
        )

    existing = _fetch_user_by_login(username_norm) or _fetch_user_by_login(email_norm)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Username or email already exists",
        )

    user_id = str(uuid.uuid4())
    password_hash = get_password_hash(password)

    with _identity_cursor() as cur:
        cur.execute(
            """
            INSERT INTO users (
                id, username, email, password_hash, is_active, is_admin, tenant_id
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            RETURNING id, username, email, password_hash, is_active, is_admin,
                      created_at, tenant_id
            """,
            (
                user_id,
                username_norm,
                email_norm,
                password_hash,
                True,
                bool(is_admin),
                tenant,
            ),
        )
        row = cur.fetchone()
        return _row_to_user(row) or {}


def authenticate_user(identifier: str, password: str) -> Optional[Dict[str, Any]]:
    user = _fetch_user_by_login(identifier)
    if not user or not user.get("is_active", True):
        # Run a dummy verify so this path costs the same as a real "wrong
        # password" — defeats username enumeration via timing side-channel.
        verify_password(password, _DUMMY_PASSWORD_HASH)
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def _user_from_api_key(raw_key: str) -> Dict[str, Any]:
    """Đổi một khoá API lấy một "người dùng" tổng hợp đại diện cho khoá đó.

    Không có tài khoản thật nào đứng sau một khoá API, nhưng toàn bộ tầng dưới
    — dependency, ghi kiểm toán, phạm vi tenant — đều nhận một dict người dùng.
    Trả về một dict cùng hình dạng là cách nối hai thứ đó mà không phải rẽ
    nhánh "nếu là khoá thì..." ở hàng chục chỗ; mỗi chỗ rẽ nhánh như thế là một
    chỗ có thể quên.

    Ba trường quyết định quyền:

    * `is_admin` LUÔN False. Một khoá API không bao giờ là quản trị viên nền
      tảng, kể cả khi người tạo ra nó là. Quyền vận hành nền tảng phải đi kèm
      một con người đang đăng nhập và, với thao tác nhạy cảm, một lần nhập lại
      mật khẩu — thứ mà một chuỗi ký tự trong biến môi trường CI không có.
    * `tenant_id` lấy từ chính khoá, nên khoá không với sang tenant khác được.
    * `api_key_scopes` là thứ `require_tenant_editor` đọc. KHÔNG giả một
      `role` để tái dùng đường tra `tenant_members`: `user_id` ở bảng đó là
      UUID, còn `id` ở đây là chuỗi `apikey:...`, nên truy vấn sẽ lỗi kiểu chứ
      không lặng lẽ trả về "không phải thành viên". Hai mặt phẳng danh tính
      khác nhau thì kiểm tra bằng hai đường khác nhau.
    """
    from app.api_keys import authenticate

    record = authenticate(raw_key)
    if not record:
        # Cùng một câu cho mọi lý do thất bại — xem `api_keys.authenticate`.
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Khoá API không hợp lệ hoặc đã bị thu hồi.",
        )

    writable = record.get("scopes") == "write"
    return {
        "id": f"apikey:{record['key_id']}",
        "username": f"apikey:{record.get('prefix') or record['key_id']}",
        "email": "",
        "is_admin": False,
        "is_active": True,
        "tenant_id": record["tenant_id"],
        "auth_method": "api_key",
        "api_key_id": record["key_id"],
        "api_key_scopes": record.get("scopes") or "read",
        "api_key_can_write": writable,
    }


def get_current_user_optional(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[Dict[str, Any]]:
    # Prefer the httpOnly access COOKIE (the SPA's session), then fall back to
    # the Authorization: Bearer header (API clients / WS fallback). Order
    # matters: browsers migrated from the legacy localStorage flow may still
    # send a STALE Bearer header on every request — if that were preferred, a
    # perfectly valid fresh cookie session would 401 forever (login -> bounce
    # loop). Pure API clients send no cookies, so they are unaffected.
    cookie_token = request.cookies.get(ACCESS_COOKIE)
    bearer_token = credentials.credentials if credentials is not None else None

    # Khoá API đi TRƯỚC, và chỉ khi không có cookie phiên.
    #
    # Thứ tự đó quan trọng: một khoá API là danh tính của MỘT HỆ THỐNG, còn
    # cookie là danh tính của MỘT NGƯỜI đang ngồi trước trình duyệt. Nếu ưu
    # tiên khoá, thì một người mở tài liệu API trong tab đang đăng nhập và dán
    # thử một lệnh curl sẽ vô tình thao tác dưới danh nghĩa khác với danh nghĩa
    # họ nhìn thấy trên màn hình.
    #
    # Khoá được nhận qua `Authorization: Bearer voya_...` chứ không phải một
    # header riêng: đó là chỗ mọi thư viện HTTP đã biết cách đặt vào, và tiền
    # tố `voya_` phân biệt nó với JWT một cách rõ ràng — JWT luôn bắt đầu bằng
    # "ey" (base64 của '{"'), nên hai loại không thể lẫn.
    if not cookie_token and bearer_token and bearer_token.startswith("voya_"):
        return _user_from_api_key(bearer_token)

    token = cookie_token or bearer_token
    if not token:
        return None

    # Two credentials naming two DIFFERENT accounts: refuse instead of silently
    # picking one. A stale or expired Bearer decodes to nothing and is ignored —
    # that is the migration case above — so this only fires when both sessions
    # are live at once: a request riding someone else's browser session, or a
    # client that mixed up whose token it was sending. Either way the server
    # cannot tell whose request this is, and guessing is how confused-deputy
    # bugs get written.
    if cookie_token and bearer_token and cookie_token != bearer_token:
        cookie_sub, bearer_sub = _subject_of(cookie_token), _subject_of(bearer_token)
        if cookie_sub and bearer_sub and cookie_sub != bearer_sub:
            logger.warning(
                "[auth] token_identity_conflict cookie_user=%s bearer_user=%s "
                "path=%s method=%s",
                cookie_sub, bearer_sub, request.url.path, request.method,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên đăng nhập không nhất quán. Vui lòng đăng nhập lại.",
            )

    payload = _decode_token(token)
    user_id = str(payload.get("sub") or "")

    # Force-logout: an admin can invalidate a user's live sessions. Tokens
    # issued before the force-logout marker are rejected; a fresh login works.
    try:
        from app import activity

        if activity.is_user_denied(user_id, payload.get("iat")):
            fl = activity.get_force_logout(user_id) or {}
            msg = "Phiên đã bị đăng xuất bởi quản trị viên"
            if fl.get("reason"):
                msg += f": {fl['reason']}"
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg)

        # Đăng xuất giết ĐÚNG phiên này, không đá thiết bị khác. Token cấp trước
        # bản vá này không có `jti` — chúng bỏ qua bước kiểm và sống nốt tối đa
        # 60 phút, đúng bằng hành vi cũ. Đó là đường chuyển tiếp, tự hết sau một
        # vòng đời access token, nên không cần cờ cấu hình nào.
        jti = payload.get("jti")
        if jti and activity.is_access_token_denied(str(jti)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên này đã đăng xuất. Vui lòng đăng nhập lại.",
            )

        # Cả HỌ bị thu hồi: refresh token của phiên này đã bị dùng lại, tức là
        # nó đã bị sao chép. Chỉ nhánh phiên đó chết; thiết bị khác không sao.
        fam = payload.get("fam")
        if fam and activity.is_token_family_denied(str(fam)):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Phiên đăng nhập đã bị thu hồi vì phát hiện dấu hiệu bị "
                       "sao chép. Vui lòng đăng nhập lại.",
            )
    except HTTPException:
        raise
    except Exception:
        pass

    user = _fetch_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )

    # Vế BỀN của thu hồi phiên, đọc từ cột vừa lấy về cùng hồ sơ người dùng ở
    # trên — không tốn thêm truy vấn nào.
    #
    # Nó nằm NGOÀI khối `try/except` phía trên một cách có chủ ý: khối đó nuốt
    # mọi lỗi để Redis chết không làm sập xác thực, nhưng ở đây dữ liệu đã nằm
    # sẵn trong tay, không có gì để hỏng, nên nuốt lỗi chỉ có thể che mất một
    # lệnh thu hồi thật.
    from app import activity as _activity

    if _activity.token_predates_marker(
        payload.get("iat"), user.get("sessions_invalid_before")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên đã bị thu hồi. Vui lòng đăng nhập lại.",
        )
    return user


def get_current_user(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    user = get_current_user_optional(request, credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not current_user.get("is_admin", False):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_tenant_editor(
    current_user: Dict[str, Any] = Depends(get_current_user),
) -> Dict[str, Any]:
    """Người dùng phải là admin/editor CỦA CHÍNH tenant mình, hoặc quản trị nền tảng.

    Bậc quyền còn thiếu giữa `get_current_user` (ai đăng nhập cũng qua) và
    `require_admin` (chỉ người vận hành nền tảng). Danh mục từ vựng nằm đúng ở
    bậc đó: một người đóng góp mẫu không được thêm lớp mới — làm thế là để một
    tài khoản bất kỳ ghi vào danh mục của cả tổ chức — nhưng người phụ trách
    dữ liệu của trường thì phải làm được mà không cần quyền nền tảng.

    Trước v4, `POST /classes/register` không có cổng nào ngoài "đã đăng nhập".
    Ghép với đường đăng ký mở cũ, nghĩa là người lạ ghi được vào danh mục của
    tổ chức đang giữ dữ liệu thật.

    Vai trò được đọc trên tenant NHÀ của người gọi (`users.tenant_id`) chứ
    không phải một tenant nêu trong yêu cầu: không endpoint nào ở bậc này nhận
    tenant từ người gọi, và nếu có thì đó mới là chỗ phải chặn.
    """
    from app.tenancy import normalize_tenant_id
    from app.vocabulary_registry import can_edit_registry

    # Khoá API là mặt phẳng danh tính KHÁC: nó không có dòng nào trong
    # `tenant_members`, và `id` của nó không phải UUID nên tra bảng đó sẽ lỗi
    # kiểu. Quyền của khoá nằm ở scope của chính nó.
    if current_user.get("auth_method") == "api_key":
        if not current_user.get("api_key_can_write"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Khoá API này chỉ có quyền đọc.",
            )
        return current_user

    tenant_id = normalize_tenant_id(current_user.get("tenant_id"))
    if not can_edit_registry(
        tenant_id, current_user.get("id"), bool(current_user.get("is_admin", False))
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Chỉ quản trị viên hoặc biên tập viên của tổ chức mới sửa được "
                "danh mục từ vựng."
            ),
        )
    return current_user


# ============================================================================
# Forgot / reset password
# ============================================================================

def _hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(identifier: str) -> Optional[Tuple[Dict[str, Any], str]]:
    """Look up the user and issue a reset token if the account exists and is active.

    Returns (user, raw_token) or None if there's no matching active account.
    Callers must respond with the same generic message either way, to avoid
    leaking which identifiers correspond to real accounts.
    """
    user = _fetch_user_by_login(identifier)
    if not user or not user.get("is_active", True):
        return None

    token = secrets.token_urlsafe(32)
    token_hash = _hash_reset_token(token)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.password_reset_token_expire_minutes
    )

    with _identity_cursor(dict_rows=False) as cur:
        cur.execute(
            """
            INSERT INTO password_reset_tokens (token_hash, user_id, expires_at)
            VALUES (%s, %s, %s)
            """,
            (token_hash, user["id"], expires_at),
        )

    return user, token


def reset_password_with_token(token: str, new_password: str) -> None:
    """Validate a reset token and set the new password. Raises HTTPException on failure."""
    if len(new_password or "") < int(settings.min_password_length):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Password must be at least {settings.min_password_length} characters",
        )

    token_hash = _hash_reset_token(token)
    invalid = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Liên kết đặt lại mật khẩu không hợp lệ hoặc đã hết hạn",
    )

    with _identity_cursor() as cur:
        cur.execute(
            """
            SELECT token_hash, user_id, expires_at, used_at
            FROM password_reset_tokens
            WHERE token_hash = %s
            """,
            (token_hash,),
        )
        row = cur.fetchone()

        if not row or row["used_at"] is not None:
            raise invalid

        expires_at = row["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        if expires_at < datetime.now(timezone.utc):
            raise invalid

        _apply_password_reset(cur, row["user_id"], new_password)


def _apply_password_reset(cur, user_id: str, new_password: str) -> None:
    """What "reset a password" means, in one place, inside one transaction.

    Three statements that must not drift apart, and now have two callers — the
    emailed-link flow above and the one-time-code flow in
    `routers/verification.py`. A second copy of this is how one of the two ends
    up changing the password without killing the sessions.
    """
    cur.execute(
        "UPDATE users SET password_hash = %s WHERE id = %s",
        (get_password_hash(new_password), user_id),
    )
    # Invalidate every outstanding reset token for this user, including the one
    # just used, so old links cannot be replayed.
    cur.execute(
        "UPDATE password_reset_tokens SET used_at = NOW() "
        "WHERE user_id = %s AND used_at IS NULL",
        (user_id,),
    )
    # Kill every existing session too. A reset is often "my account may be
    # compromised"; leaving an attacker's still-valid refresh token alive would
    # defeat the point. Same transaction as the password change, so it is
    # all-or-nothing.
    cur.execute(
        "UPDATE refresh_tokens SET revoked_at = NOW() "
        "WHERE user_id = %s AND revoked_at IS NULL",
        (user_id,),
    )
    # Any outstanding one-time code is spent too: a reset completed by one
    # channel must not leave a live code from another still able to reset again.
    cur.execute(
        "UPDATE verification_codes SET consumed_at = NOW() "
        "WHERE user_id = %s AND purpose = 'reset_password' AND consumed_at IS NULL",
        (user_id,),
    )
    # Và giết luôn access token đang sống.
    #
    # Ba câu trên chỉ cắt được đường LÀM MỚI phiên. Access token là JWT không
    # trạng thái, nên nếu chỉ thu hồi refresh token thì kẻ đang chiếm tài khoản
    # vẫn thao tác bình thường thêm 60 phút nữa — với một thao tác mà lý do
    # thường là "tôi nghi mình bị chiếm tài khoản", 60 phút là quá dài.
    #
    # Ở đây "đá mọi thiết bị" mới là hành vi ĐÚNG, khác hẳn với đăng xuất (xem
    # `deny_this_access_token`). Đặt mốc trong CÙNG giao dịch với việc đổi mật
    # khẩu, nên không có cửa sổ nào mật khẩu đã đổi mà phiên cũ còn sống.
    cur.execute(
        "UPDATE users SET sessions_invalid_before = NOW() WHERE id = %s",
        (user_id,),
    )


def set_password_and_revoke_sessions(user_id: str, new_password: str) -> None:
    """Public entry point for the code-based reset flow."""
    with _identity_cursor(dict_rows=False) as cur:
        _apply_password_reset(cur, str(user_id), new_password)


# ============================================================================
# Refresh tokens (cookie session flow)
# ============================================================================

def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


#: Vé tạm giữa hai bước đăng nhập. 5 phút: đủ để mở ứng dụng xác thực và gõ 6
#: chữ số, quá ngắn để ai đó nhặt được vé từ nhật ký mà còn dùng kịp.
TWO_FACTOR_CHALLENGE_MINUTES = 5


def create_2fa_challenge(user_id: str) -> str:
    """Vé chứng minh "mật khẩu ĐÃ đúng, còn thiếu bước hai".

    Là JWT ký chứ không phải một chuỗi ngẫu nhiên lưu trong CSDL: nó sống 5
    phút và không cần thu hồi, nên một bảng chỉ thêm việc phải dọn.

    `typ` phải là `2fa_challenge` và `verify_2fa_challenge` kiểm đúng giá trị
    đó. Thiếu bước kiểm ấy thì vé này dùng thay access token được — tức là bước
    hai tự vô hiệu hoá chính nó.
    """
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "typ": "2fa_challenge",
            "iat": now,
            "exp": now + timedelta(minutes=TWO_FACTOR_CHALLENGE_MINUTES),
        },
        settings.secret_key, algorithm=settings.algorithm)


def verify_2fa_challenge(token: str) -> Optional[str]:
    """`user_id` của một vé còn hiệu lực, hoặc None."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm],
            options={"verify_aud": False})
    except JWTError:
        return None
    if payload.get("typ") != "2fa_challenge":
        return None
    return str(payload.get("sub") or "") or None


#: Vé giữa "đã nhập đúng mã khôi phục" và "đã đặt mật khẩu mới".
#:
#: Vì sao phải có nó: nếu mã và mật khẩu mới đi chung MỘT request thì màn hình
#: buộc phải hỏi cả hai cùng lúc, và người dùng chỉ biết mã sai SAU khi đã nghĩ
#: xong một mật khẩu. Tách ra thì mã được trả lời ngay, đúng như Google/Facebook.
#:
#: 5 phút, không thu hồi được: đủ để gõ một mật khẩu, quá ngắn để ai nhặt được
#: vé còn dùng kịp. Thử thách OTP đã bị `otp.verify` tiêu trước khi vé này ra
#: đời, nên một vé bị mất KHÔNG cộng thêm lượt đoán mã cho ai cả.
PASSWORD_RESET_TICKET_MINUTES = 5


def create_password_reset_ticket(user_id: str) -> str:
    """Vé chứng minh "mã khôi phục ĐÃ đúng, còn thiếu mật khẩu mới"."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "typ": "pw_reset",
            "iat": now,
            "exp": now + timedelta(minutes=PASSWORD_RESET_TICKET_MINUTES),
        },
        settings.secret_key, algorithm=settings.algorithm)


def verify_password_reset_ticket(token: str) -> Optional[str]:
    """`user_id` của một vé còn hiệu lực, hoặc None.

    Kiểm `typ` là bắt buộc, cùng lý do như `verify_2fa_challenge`: mọi token
    trong hệ thống ký bằng một khoá, nên chữ ký hợp lệ chỉ chứng minh "chỗ này
    phát ra nó", không chứng minh nó được phát ra ĐỂ LÀM GÌ. Chiều ngược lại đã
    được `_decode_token` chặn — vé này không dùng thay access token được.
    """
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm],
            options={"verify_aud": False})
    except JWTError:
        return None
    if payload.get("typ") != "pw_reset":
        return None
    return str(payload.get("sub") or "") or None


def new_session_family() -> str:
    """Định danh cho MỘT lần đăng nhập. Refresh token và access token của cùng
    phiên mang chung giá trị này, nên thu hồi được đúng một phiên."""
    return str(uuid.uuid4())


def create_refresh_token(user_id: str, family_id: Optional[str] = None) -> str:
    """Issue a new opaque refresh token, storing only its hash. Returns the raw
    token (to be set as an httpOnly cookie).

    `family_id` omitted = a NEW login, so a new family is born. Rotation passes
    the parent's family through, which is what lets reuse detection burn every
    token descended from one stolen cookie without touching other devices.
    """
    raw = secrets.token_urlsafe(48)
    token_hash = _hash_token(raw)
    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.refresh_token_expire_minutes
    )
    fam = str(family_id) if family_id else str(uuid.uuid4())
    with _identity_cursor(dict_rows=False) as cur:
        cur.execute(
            """
            INSERT INTO refresh_tokens (token_hash, user_id, expires_at, family_id)
            VALUES (%s, %s, %s, %s)
            """,
            (token_hash, user_id, expires_at, fam),
        )
    return raw


def _burn_token_family(cur, family_id: Optional[str], token_hash: str,
                       user_id: str) -> None:
    """A revoked token came back outside the grace window: treat it as stolen.

    Revoking the whole family is the point. Revoking only the presented token
    would leave the thief's *successor* token alive — and the thief is, by
    construction, the one holding the newest token in the family.
    """
    if family_id:
        cur.execute(
            "UPDATE refresh_tokens SET revoked_at = COALESCE(revoked_at, NOW()), "
            "reuse_detected_at = NOW() WHERE family_id = %s",
            (str(family_id),),
        )
    else:
        # Token cấp trước lần triển khai này, chưa có họ. Chỉ đốt được chính nó.
        cur.execute(
            "UPDATE refresh_tokens SET revoked_at = COALESCE(revoked_at, NOW()), "
            "reuse_detected_at = NOW() WHERE token_hash = %s",
            (token_hash,),
        )
    # Access token của CHÍNH họ này cũng phải chết. Chúng stateless nên tự chúng
    # không biết refresh token tổ tiên vừa bị đốt.
    #
    # Chặn theo họ chứ KHÔNG gọi `force_logout_user`, vì hai lý do tách biệt và
    # cả hai đều đủ để loại nó:
    #
    #  1. `force_logout_user` mở một kết nối Postgres MỚI để thu hồi token, còn
    #     hàm này đang chạy bên trong giao dịch đang giữ khoá trên đúng những
    #     dòng đó. Kết nối thứ hai chờ khoá của kết nối thứ nhất, kết nối thứ
    #     nhất chờ hàm trả về: treo vĩnh viễn. Đã dựng lại được bằng test.
    #  2. Nó đá MỌI thiết bị. Người dùng bị trộm phiên trên điện thoại không có
    #     lý do gì phải văng khỏi máy tính — đó là trừng phạt nạn nhân.
    try:
        from app import activity

        if family_id:
            activity.deny_token_family(str(family_id))
    except Exception:
        logger.exception("[auth] chan ho token that bai family=%s", family_id)

    # ERROR chứ không phải WARNING: đây là dấu hiệu một phiên đã bị sao chép, và
    # nó phải nổi lên trong cảnh báo chứ không chìm trong nhật ký.
    logger.error(
        "[auth] refresh_reuse_detected user=%s family=%s — da thu hoi ca ho",
        user_id, family_id,
    )


def rotate_refresh_token(
    raw_token: str,
) -> Optional[Tuple[Dict[str, Any], str, str]]:
    """Validate a refresh token, revoke it, and mint a replacement.

    Returns (user, new_raw_token, family_id) or None if the token is missing /
    expired / belongs to a burnt family / belongs to an inactive user.

    `family_id` is returned so the caller can stamp it onto the new ACCESS token
    too. Without that, reuse detection can revoke the refresh lineage but has no
    way to name the access tokens minted from it.

    Rotation on its own is only half the mechanism. Without reuse detection the
    outcome is inverted: a thief who calls /refresh first walks away with a
    valid new token while the real user's next refresh 401s and logs them out.
    RFC 9700 §4.14.2 asks for the whole family to be revoked instead. See
    docs/03-security/AUTH_TOKEN_LIFECYCLE.md §1 for the full attack trace.
    """
    if not raw_token:
        return None
    token_hash = _hash_token(raw_token)

    with _identity_cursor() as cur:
        cur.execute(
            """
            SELECT token_hash, user_id, expires_at, revoked_at, family_id,
                   reuse_detected_at
            FROM refresh_tokens
            WHERE token_hash = %s
            """,
            (token_hash,),
        )
        row = cur.fetchone()
        if not row:
            return None

        user_id = str(row["user_id"])
        family_id = row["family_id"]

        # Họ đã bị đốt: chết vĩnh viễn, kể cả khi token còn hạn. Kiểm TRƯỚC hạn
        # dùng để một họ bị đốt không hồi sinh được bằng bất kỳ đường nào.
        if row["reuse_detected_at"] is not None:
            return None

        expires_at = row["expires_at"]
        if expires_at.tzinfo is None:
            expires_at = expires_at.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        if expires_at < now:
            return None

        revoked_at = row["revoked_at"]
        if revoked_at is not None:
            if revoked_at.tzinfo is None:
                revoked_at = revoked_at.replace(tzinfo=timezone.utc)
            age = (now - revoked_at).total_seconds()
            if age > max(0, int(settings.refresh_grace_seconds)):
                _burn_token_family(cur, family_id, token_hash, user_id)
                return None
            # Trong cửa sổ ân hạn — gần như chắc chắn là hai tab đua nhau. Cấp
            # token mới cùng họ.
            #
            # KHÔNG trả lại được đúng token kế nhiệm cho tab thua, vì CSDL chỉ
            # giữ băm chứ không giữ token thô. Đó là lý do cách xử lý là *cấp
            # mới*, không phải *trả lại cái cũ*.
            logger.info(
                "[auth] refresh_grace_hit user=%s family=%s age=%.1fs",
                user_id, family_id, age,
            )

        user = _fetch_user_by_id(user_id)
        if not user or not user.get("is_active", True):
            return None

        new_raw = secrets.token_urlsafe(48)
        new_hash = _hash_token(new_raw)
        new_expires = now + timedelta(
            minutes=settings.refresh_token_expire_minutes
        )
        # `revoked_at` giữ nguyên nếu đã có: mốc revoke đầu tiên là mốc đóng cửa
        # sổ ân hạn, ghi đè nó sẽ làm cửa sổ trượt theo mỗi lần đua và một token
        # bị trộm có thể sống mãi bằng cách gọi lại đều đặn.
        cur.execute(
            "UPDATE refresh_tokens "
            "SET revoked_at = COALESCE(revoked_at, NOW()), replaced_by = %s "
            "WHERE token_hash = %s",
            (new_hash, token_hash),
        )
        cur.execute(
            """
            INSERT INTO refresh_tokens (token_hash, user_id, expires_at, family_id)
            VALUES (%s, %s, %s, %s)
            """,
            (new_hash, row["user_id"], new_expires, family_id),
        )
        return user, new_raw, str(family_id or "")


def purge_expired_refresh_tokens(retain_days: int = 7) -> int:
    """Xoá refresh token đã hết hạn quá `retain_days` ngày. Trả số dòng đã xoá.

    Bảng này chỉ lớn lên: mỗi lần đăng nhập VÀ mỗi lần xoay đều thêm một dòng,
    `revoked_at` chỉ là đánh dấu chứ không xoá gì. Access sống 60 phút nên một
    người dùng hoạt động sinh khoảng một dòng mỗi giờ — 100 người × 8 giờ/ngày
    ≈ 800 dòng/ngày, ~290 nghìn dòng/năm.

    Giữ lại 7 ngày sau khi hết hạn chứ không xoá ngay, vì chuỗi `replaced_by` là
    thứ duy nhất dựng lại được đường xoay token khi điều tra một vụ tái sử dụng.
    Xoá sạch tức thì là vứt đi bằng chứng của chính cơ chế vừa dựng ở trên.
    """
    days = max(0, int(retain_days))
    with _identity_cursor(dict_rows=False) as cur:
        cur.execute(
            "DELETE FROM refresh_tokens "
            "WHERE expires_at < NOW() - make_interval(days => %s)",
            (days,),
        )
        return int(cur.rowcount or 0)


def deny_this_access_token(raw_token: str) -> bool:
    """Chặn access token đang cầm trên tay (đăng xuất). Best-effort, không ném.

    Chữ ký được XÁC MINH trước khi lấy `jti`. Nếu đọc claim mà không xác minh,
    bất kỳ ai cũng gửi được một token tự chế mang `jti` tuỳ chọn và bơm rác vào
    danh sách chặn — hoặc tệ hơn, chặn `jti` của người khác nếu đoán trúng.

    Token hết hạn thì giải mã thất bại, và đó là kết quả đúng: nó đã chết, không
    có gì để chặn.
    """
    if not raw_token:
        return False
    try:
        payload = jwt.decode(
            raw_token,
            settings.secret_key,
            algorithms=[settings.algorithm],
            options={"verify_aud": False},
        )
    except JWTError:
        return False

    jti = payload.get("jti")
    if not jti:
        return False  # token cấp trước bản vá — không có gì để chặn
    try:
        from app import activity

        return activity.deny_access_token(str(jti), payload.get("exp"))
    except Exception:
        logger.exception("[auth] chan access token that bai")
        return False


def revoke_refresh_token(raw_token: str) -> None:
    """Mark a refresh token revoked (logout). Best-effort; never raises."""
    if not raw_token:
        return
    token_hash = _hash_token(raw_token)
    try:
        with _identity_cursor(dict_rows=False) as cur:
            cur.execute(
                """
                UPDATE refresh_tokens
                SET revoked_at = NOW()
                WHERE token_hash = %s AND revoked_at IS NULL
                """,
                (token_hash,),
            )
    except Exception:
        pass