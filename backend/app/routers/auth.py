import hashlib
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status, Depends  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel, Field  # pyright: ignore[reportMissingImports]

from app import tenant_admin
from app.config import settings
from app.auth import (
    _fetch_user_by_id,
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_2fa_challenge,
    verify_2fa_challenge,
    new_session_family,
    create_user,
    get_current_user,
    request_password_reset,
    reset_password_with_token,
    revoke_refresh_token,
    rotate_refresh_token,
    verify_password,
)
from app.cookie_auth import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    generate_csrf_token,
    set_auth_cookies,
)
from app.public_url import resolve_frontend_base_url
from app.rate_limit import (
    check_login_allowed,
    check_register_allowed,
    client_ip,
    enforce_ip_limit,
    register_account_created,
    register_failed_login,
    reset_login_attempts,
)
from app.email_service import send_password_reset_email

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

# Generic response for forgot-password so the API never reveals whether an
# identifier corresponds to a real account (prevents user enumeration).
_FORGOT_PASSWORD_GENERIC_MESSAGE = (
    "Nếu tài khoản tồn tại, chúng tôi đã gửi email hướng dẫn đặt lại mật khẩu."
)


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=128)
    # An invitation token, when the person is joining an institution rather than
    # signing up openly. There is deliberately NO `tenant_id` field: a caller who
    # could name their own tenant would join any tenant they can guess the id of,
    # and tenant ids appear in URLs.
    invitation_token: Optional[str] = Field(None, max_length=512)

    # Tên tổ chức, dùng KHI VÀ CHỈ KHI không có lời mời: đăng ký tự phục vụ tạo
    # một tenant mới và đây là tên hiển thị của nó. Vẫn không có `tenant_id` —
    # mã tenant do máy chủ sinh, kèm hậu tố ngẫu nhiên, nên người gọi không
    # chọn được mình rơi vào đâu và cũng không dò được ai đã có mặt.
    #
    # Bỏ trống thì lấy username làm tên tổ chức. Một người thu dữ liệu cá nhân
    # không cần bịa ra tên trường để dùng được sản phẩm.
    organization_name: Optional[str] = Field(None, max_length=120)

    # Số hiệu bản Điều khoản và Quyền riêng tư mà người dùng ĐÃ ĐỌC.
    #
    # Không phải boolean. Một cờ "đã tích" trả lời được "có bấm không" nhưng
    # không trả lời được "bấm vào cái gì" — và ngày văn bản đổi, mọi chữ ký thu
    # được trở nên vô nghĩa. Số hiệu được đối chiếu với bản đang hiệu lực ở
    # server: một biểu mẫu cũ còn mở trong tab sẽ gửi số cũ, và chấp nhận nó là
    # thu chữ ký cho một bản đã bị thay thế.
    accepted_terms_version: Optional[str] = Field(None, max_length=64)
    accepted_privacy_version: Optional[str] = Field(None, max_length=64)


class LoginRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=128)


class UserOut(BaseModel):
    id: str
    username: str
    email: str
    is_active: bool
    is_admin: bool
    created_at: Optional[datetime] = None
    # Which institution this account belongs to. Returned so the SPA can show it
    # after registration — the person who followed an invitation link needs to
    # see they landed in the right place, and the failure mode this catches
    # (silently registered into the public tenant) is otherwise invisible.
    tenant_id: Optional[str] = None


class MessageResponse(BaseModel):
    message: str


def _public_user(user: dict) -> dict:
    """Hồ sơ người dùng đã lọc, dùng cho endpoint KHÔNG khai `response_model`.

    `UserOut` là danh sách CHO PHÉP, và nó là thứ duy nhất ngăn `password_hash`
    đi ra ngoài — `auth._row_to_user` mang cột đó theo trên mọi hồ sơ, cố ý, vì
    `authenticate_user` cần nó.

    Endpoint nào bỏ `response_model` thì phải gọi hàm này. `/auth/login` từng bị
    đúng lỗi đó trong vài phút: bỏ `response_model=UserOut` để trả được hai hình
    dạng (hồ sơ hoặc vé hai bước) đã vô tình gỡ luôn bộ lọc, và băm bcrypt đi ra
    theo mọi lượt đăng nhập thành công.
    """
    return UserOut(**user).model_dump() if hasattr(UserOut, "model_dump") \
        else UserOut(**user).dict()


def _validate_consents(payload: "RegisterRequest") -> dict:
    """Kiểm hai chấp thuận bắt buộc TRƯỚC khi tạo tài khoản.

    Trả về `{kind: version}` đã đối chiếu với bản đang hiệu lực, hoặc ném lỗi.

    **Cưỡng chế bật khi deployment đã CÔNG BỐ điều khoản, không phải luôn luôn.**

    Bản đầu tiên của hàm này từ chối đăng ký (503) khi chưa có văn bản nào. Nghe
    thì chặt, nhưng nó sai ở hai đầu: một bản triển khai mới không onboard được
    ai cho tới khi người vận hành chạy một lệnh CLI, và "chưa công bố điều
    khoản" bị đối xử như một sự cố trong khi nó chỉ là một deployment chưa dùng
    tính năng này.

    Cách đọc đúng: **công bố văn bản CHÍNH LÀ hành động bật cưỡng chế.** Chưa
    công bố thì không có gì để đồng ý. Công bố rồi thì mọi tài khoản mới phải
    đồng ý, và số hiệu được đối chiếu ở server.

    Rủi ro còn lại — quên công bố rồi tưởng đang thu chấp thuận — được bịt ở
    tầng khác: `verify_deployment` báo ĐỎ khi thiếu văn bản bắt buộc, nên nó lộ
    ra lúc triển khai chứ không lộ ra ở toà.
    """
    from app import legal

    if legal.missing_for_registration():
        # Deployment chưa công bố điều khoản. Ghi ở mức WARNING chứ không im
        # lặng: nếu ai đó nghĩ chấp thuận đang được thu, dòng log này là chỗ
        # đầu tiên họ tìm ra sự thật.
        logger.warning(
            "[LEGAL] chưa công bố %s — đăng ký KHÔNG thu chấp thuận nào",
            ", ".join(legal.missing_for_registration()),
        )
        return {}

    supplied = {
        "terms": payload.accepted_terms_version,
        "privacy": payload.accepted_privacy_version,
    }
    for kind in legal.REQUIRED_AT_REGISTRATION:
        doc = legal.current_document(kind)
        version = (supplied.get(kind) or "").strip()
        if not version:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "consent_required",
                    "kind": kind,
                    "version": doc["version"],
                    "url": doc["url"],
                    "message": "Bạn cần đọc và đồng ý trước khi tạo tài khoản.",
                },
            )
        if version != str(doc["version"]):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "stale_version",
                    "kind": kind,
                    "version": doc["version"],
                    "url": doc["url"],
                    "message": "Văn bản đã được cập nhật. Hãy tải lại trang và "
                               "đọc bản mới.",
                },
            )
        supplied[kind] = version
    return supplied


def _record_consents(user_id: str, consents: dict, request: Request) -> None:
    """Ghi chấp thuận kèm bằng chứng: thời điểm, băm IP, user agent.

    Băm IP chứ không lưu IP: bằng chứng cần trả lời "có phải cùng một nơi
    không", và câu hỏi đó chỉ cần SO SÁNH. Lưu địa chỉ thô là thu thêm dữ liệu
    cá nhân cho một mục đích không đòi hỏi nó.
    """
    from app import legal
    from app.rate_limit import client_ip

    ip_hash = hashlib.sha256(
        f"{client_ip(request)}|{user_id}".encode("utf-8")).hexdigest()
    agent = (request.headers.get("user-agent") or "")[:500]
    for kind, version in consents.items():
        legal.record_consent(user_id, kind, version,
                             ip_hash=ip_hash, user_agent=agent)


def _send_welcome_verification(user: dict) -> None:
    """Gửi mã xác minh ngay khi tài khoản vừa tạo.

    Không có bước này thì `REQUIRE_EMAIL_VERIFICATION` là một cái bẫy: người
    dùng đăng ký xong, đăng nhập, bị từ chối vì chưa xác minh — và không có gì
    trong hộp thư để họ xác minh bằng. Mã phải đi CÙNG lúc tài khoản ra đời,
    không phải chờ họ tự tìm ra một nút ở đâu đó.

    **Không bao giờ làm hỏng việc đăng ký.** Tài khoản đã tồn tại và giao dịch
    đã xong; ném lỗi ở đây trả về 500 cho một request đã thành công, và người
    dùng sẽ thử đăng ký lại rồi đụng chính username họ vừa chiếm. SMTP hỏng là
    việc của người vận hành, và luôn còn đường `/auth/verify/send`.
    """
    from app import otp
    from app.email_service import send_verification_code_email

    try:
        _, code = otp.issue(
            user_id=user["id"], purpose="verify_email",
            channel="email", destination=user["email"],
        )
        send_verification_code_email(user["email"], code, "verify_email")
    except Exception as exc:
        # Chỉ ghi TÊN LOẠI ngoại lệ. Thông điệp của một lỗi SMTP có thể mang
        # theo cả nội dung thư — và nội dung thư ở đây chính là mã.
        logger.warning(
            "[REGISTER] không gửi được mã xác minh cho %s: %s",
            user["id"], type(exc).__name__,
        )


def _deactivate_stranded_account(user_id: str, *, reason: str) -> None:
    """Đóng một tài khoản vừa tạo mà không gắn được vào tổ chức nào.

    Nó vẫn đang mang tenant gốc, và đó là trạng thái duy nhất không được phép
    tồn tại ở dạng SỐNG. Vô hiệu hoá là thao tác nhỏ nhất đạt được điều đó —
    xoá hẳn thì mất luôn dấu vết chấp thuận điều khoản vừa ghi, thứ có thể cần
    tới nếu người dùng khiếu nại.

    Nuốt lỗi có chủ ý: hàm này chạy trong nhánh xử lý một lỗi khác, và để nó
    ném tiếp sẽ thay thế nguyên nhân thật bằng một lỗi thứ cấp.
    """
    try:
        from app.storage.metadata_db import _execute

        _execute("UPDATE users SET is_active = FALSE WHERE id = %s", (str(user_id),))
        logger.error(
            "[REGISTER] tài khoản %s bị vô hiệu hoá vì không tạo được tổ chức: %s",
            user_id, reason,
        )
    except Exception as exc:
        # Đây là trường hợp xấu nhất: một tài khoản sống trong tenant gốc.
        # Không im lặng được — nó phải hiện ra ở cảnh báo để có người xử lý.
        logger.critical(
            "[REGISTER] KHÔNG vô hiệu hoá được tài khoản %s đang kẹt trong tenant "
            "gốc (%s); cần xử lý bằng tay",
            user_id, type(exc).__name__,
        )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request):
    # Two-stage: a tight per-minute cap on ATTEMPTS (stops a script hammering
    # the endpoint) and a loose daily cap on accounts actually CREATED. The
    # daily one only counts real accounts, so a failed validation never pushes a
    # shared campus address towards it — see rate_limit.check_register_allowed.
    ip = check_register_allowed(request)

    # The invitation is validated BEFORE the account is created. Creating first
    # and then discovering the token is stale would leave a real account stranded
    # in the public tenant — and the caller, seeing an error, would try again and
    # collide with the username they just took.
    #
    # Không lời mời thì đăng ký tự phục vụ phải đang bật. Kiểm TRƯỚC khi tạo
    # tài khoản, cùng lý do với lời mời ngay bên dưới: phát hiện sau sẽ để lại
    # một tài khoản thật mà người dùng không biết mình đã có.
    #
    # Không còn nhánh thứ ba. Trước v4, thiếu lời mời nghĩa là rơi vào tenant
    # gốc — tổ chức đang giữ toàn bộ dữ liệu thật — và tài khoản đó hoạt động
    # ngay vì `users.is_active` mặc định TRUE. Bất kỳ ai đăng ký được đều thành
    # thành viên của tổ chức đó và ghi được vào danh mục lớp của nó.
    if not payload.invitation_token and not settings.self_serve_signup:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Nền tảng đang chỉ nhận thành viên qua lời mời.",
        )

    invitation = None
    if payload.invitation_token:
        try:
            invitation = tenant_admin.peek_invitation(payload.invitation_token)
        except tenant_admin.TenantError as exc:
            raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
        if (invitation.get("email") or "").lower() != (payload.email or "").strip().lower():
            # Same refusal as consume_invitation, made here so the account is
            # never created. An invitation names a person; whoever holds the URL
            # is not necessarily that person.
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Lời mời này được gửi cho một địa chỉ email khác.",
            )

    # Điều khoản được kiểm TRƯỚC khi tài khoản tồn tại, cùng lý do với lời mời
    # ở trên: tạo trước rồi mới phát hiện thiếu chấp thuận sẽ để lại một tài
    # khoản thật mà người dùng không biết mình đã có, và lần thử lại sẽ đụng
    # chính username họ vừa chiếm.
    consents = _validate_consents(payload)

    user = create_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        is_admin=False,
        # Still the bootstrap tenant when there is no invitation. consume_invitation
        # moves the account immediately below; passing the tenant here as well
        # would duplicate the decision in two places.
        tenant_id=None,
    )

    # Ghi chấp thuận NGAY sau khi có user_id. Không gộp được vào một giao dịch
    # với `create_user` (nó tự quản giao dịch của mình), nên thứ tự là thứ bảo
    # vệ: kiểm ở trên đã bảo đảm hai bản văn tồn tại và số hiệu đúng, nên bước
    # ghi này chỉ hỏng khi cơ sở dữ liệu hỏng.
    _record_consents(user["id"], consents, request)

    if payload.invitation_token:
        try:
            tenant_admin.consume_invitation(
                payload.invitation_token, email=payload.email, user_id=user["id"]
            )
        except tenant_admin.TenantError as exc:
            # The account exists and the invitation did not attach. Reported
            # rather than swallowed: the person is registered in the public
            # tenant and an operator has to re-invite. Silently returning success
            # would leave them looking at the wrong institution's data with no
            # error anywhere.
            logger.warning(
                "[REGISTER] account %s created but invitation did not attach: %s",
                user["id"], exc,
            )
            raise HTTPException(
                status_code=exc.status_code,
                detail=f"Tài khoản đã được tạo nhưng chưa gắn được vào tổ chức: {exc}",
            ) from exc
        # Re-read so the response carries the tenant the account actually ended
        # up in, not the one it was created in a moment ago.
        user = _fetch_user_by_id(user["id"]) or user
    else:
        # Tự phục vụ: tổ chức riêng, người này làm chủ.
        #
        # Tài khoản được tạo TRƯỚC tenant, nên trong khoảnh khắc giữa hai bước
        # nó vẫn mang tenant gốc. Nếu bước tạo tenant hỏng, tài khoản bị VÔ
        # HIỆU HOÁ chứ không để nguyên: một tài khoản chết trong tenant gốc là
        # phiền toái phải khắc phục bằng tay, còn một tài khoản SỐNG trong
        # tenant gốc đúng là lỗ hổng mà cả đoạn này sinh ra để bịt. Thứ tự
        # ngược lại — tenant trước, tài khoản sau — chỉ đổi chỗ vấn đề: một
        # username trùng sẽ để lại tenant mồ côi mà `ON DELETE RESTRICT` không
        # cho dọn, vì danh mục đã được sao chép vào đó.
        try:
            tenant = tenant_admin.create_self_serve_tenant(
                user["id"],
                display_name=(payload.organization_name or "").strip() or payload.username,
            )
        except tenant_admin.TenantError as exc:
            _deactivate_stranded_account(user["id"], reason=str(exc))
            raise HTTPException(
                status_code=exc.status_code,
                detail=f"Không tạo được tổ chức cho tài khoản: {exc}",
            ) from exc
        except Exception as exc:
            _deactivate_stranded_account(user["id"], reason=type(exc).__name__)
            raise
        logger.info(
            "[REGISTER] tài khoản %s tự tạo tổ chức %s", user["id"], tenant["tenant_id"]
        )
        user = _fetch_user_by_id(user["id"]) or user

    _send_welcome_verification(user)

    register_account_created(ip)
    return user


def _access_for(user: dict, family_id: str = "") -> str:
    """`family_id` gắn access token vào ĐÚNG phiên đã sinh ra nó.

    Nhờ đó, khi phát hiện refresh token bị dùng lại, hệ thống thu hồi được cả
    access token của nhánh phiên đó mà không đụng tới thiết bị khác của cùng
    người dùng. Bỏ trống thì token vẫn hợp lệ — chỉ là không thu hồi theo phiên
    được, đúng bằng hành vi trước bản vá.
    """
    data = {
        "sub": user["id"],
        "username": user["username"],
        "email": user["email"],
        "is_admin": user["is_admin"],
    }
    if family_id:
        data["fam"] = family_id
    return create_access_token(
        data=data,
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


@router.post("/login")
def login(payload: LoginRequest, request: Request, response: Response):
    """Đăng nhập. Trả về hồ sơ người dùng, HOẶC một vé bước hai.

    `response_model=UserOut` đã được BỎ ở đây vì endpoint giờ có hai hình dạng
    trả về. Hình dạng của đường thành công thông thường không đổi một chữ nào,
    nên giao diện cũ chạy nguyên; chỉ khi tài khoản bật 2FA mới nhận
    `{"two_factor_required": true, "challenge": ...}`.

    **Vì thế đường thành công PHẢI trả `_public_user(user)`, không phải `user`.**
    `response_model` là thứ duy nhất lọc `password_hash` ra khỏi phản hồi, và bỏ
    nó đi đã vô tình gỡ luôn bộ lọc đó. Ghim ở
    `test_session_lifecycle.py::TestKhongRoBamMatKhau`.
    """
    ip = client_ip(request)
    # Reject early (before bcrypt) if this IP or identifier is already locked.
    check_login_allowed(ip, payload.identifier)

    user = authenticate_user(payload.identifier, payload.password)
    if not user:
        # Count the failure against both IP and identifier, then fail generically.
        register_failed_login(ip, payload.identifier)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
        )

    # Successful login clears the counters so the user isn't locked next time.
    reset_login_attempts(ip, payload.identifier)

    # Unverified address, if the deployment demands one. Enforced HERE and
    # nowhere else: one gate on the way in beats a decorator on each of eighty
    # endpoints, where the one that gets forgotten is the hole.
    #
    # Placed AFTER the password check on purpose. Refusing before it would turn
    # this endpoint into an oracle for "is this address registered but
    # unverified?" — answerable without knowing the password. Placed BEFORE the
    # cookies are set, so no session exists to clean up.
    if settings.require_email_verification and not user.get("email_verified_at"):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                "Địa chỉ email của tài khoản chưa được xác minh. "
                "Hãy dùng chức năng khôi phục tài khoản để nhận mã xác minh."
            ),
        )

    # Correct password but the account is locked by an admin → say so clearly.
    try:
        from app import activity

        lock = activity.get_user_lock(user["id"])
        if lock:
            reason = lock.get("reason") or "vi phạm quy định"
            msg = f"Tài khoản của bạn đã bị khóa. Lý do: {reason}"
            until = activity._fmt_until(lock.get("until") or 0)
            if until:
                msg += f" (mở lại lúc {until})"
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=msg)
    except HTTPException:
        raise
    except Exception:
        pass

    # Deliver the session via httpOnly cookies (no token in the body → JS/XSS
    # can't read it). The body carries only the user profile.
    # Bước hai, nếu người dùng đã bật. Đặt SAU mọi lượt kiểm khác và TRƯỚC khi
    # đặt cookie: tới đây mật khẩu đã đúng, tài khoản không bị khoá, thư đã xác
    # minh — nhưng chưa có phiên nào để phải dọn nếu bước hai thất bại.
    #
    # Lỗi ở đây fail-CLOSED: nếu không đọc được trạng thái 2FA thì từ chối đăng
    # nhập, chứ không cho qua. Ngược lại là biến một sự cố cơ sở dữ liệu thành
    # cách vô hiệu hoá 2FA của cả hệ thống.
    # Giá trị đến KÈM `authenticate_user` (LEFT JOIN `user_totp`), không phải từ
    # một truy vấn riêng. Bản đầu gọi `two_factor.is_enabled()` ở đây và sai theo
    # hai cách: thêm một truy vấn vào đường nóng, và biến mọi trục trặc thoáng
    # qua của CSDL thành 503 — tức là "không ai đăng nhập được".
    #
    # `None` = hồ sơ đến từ một đường KHÔNG join (ví dụ `_fetch_user_by_id`), tức
    # là LỖI LẬP TRÌNH, không phải trục trặc thoáng qua — truy vấn lấy hồ sơ vừa
    # thành công xong.
    #
    # Từ chối cấp phiên, và nói thật lý do. Hai lựa chọn kia đều sai: coi như
    # "chưa bật" là bỏ qua 2FA cho mọi người; coi như "đã bật" là đẩy họ tới một
    # bước hai họ KHÔNG hoàn tất được (không có bí mật TOTP nào), tức khoá luôn
    # tài khoản mà vẫn không tăng thêm an toàn.
    needs_2fa = user.get("two_factor_enabled")
    if needs_2fa is None:
        logger.error(
            "[auth] ho so thieu two_factor_enabled user=%s — duong lay ho so sai",
            user["id"])
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không xác định được thiết lập bảo mật của tài khoản.",
        )

    if needs_2fa:
        return {
            "two_factor_required": True,
            "challenge": create_2fa_challenge(user["id"]),
        }

    _issue_session(response, request, user)
    # `_public_user`, KHÔNG phải `user`: endpoint này không có `response_model`
    # nên không có gì lọc `password_hash` ra hộ.
    return _public_user(user)


def _issue_session(response: Response, request: Request, user: dict) -> None:
    """Đặt bộ ba cookie cho một phiên mới. Một chỗ, hai đường gọi tới.

    Đăng nhập một bước và đăng nhập hai bước phải sinh ra phiên GIỐNG HỆT nhau;
    hai bản sao của đoạn này là cách một trong hai đường lặng lẽ quên `family_id`
    và mất khả năng thu hồi theo phiên.
    """
    fam = new_session_family()
    set_auth_cookies(
        response,
        access_token=_access_for(user, fam),
        refresh_token=create_refresh_token(user["id"], family_id=fam),
        csrf_token=generate_csrf_token(),
        request=request,
    )


class TwoFactorLoginRequest(BaseModel):
    challenge: str = Field(..., min_length=10)
    code: str = Field(..., min_length=6, max_length=11)


@router.post("/login/2fa")
def login_two_factor(payload: TwoFactorLoginRequest,
                     request: Request, response: Response):
    """Bước hai: đổi vé + mã lấy một phiên thật.

    Chấp nhận cả mã TOTP 6 chữ số lẫn mã khôi phục dạng `xxxxx-xxxxx`. Người
    mất điện thoại mà không có đường vào nào khác thì 2FA đã biến từ lớp bảo vệ
    thành cách tự khoá mình ra ngoài.
    """
    from app import two_factor

    ip = client_ip(request)
    # Cùng bộ đếm với bước một: không có nó, kẻ tấn công đã có mật khẩu chỉ cần
    # dò một triệu khả năng của 6 chữ số mà không gặp giới hạn nào.
    check_login_allowed(ip, payload.challenge[:64])

    user_id = verify_2fa_challenge(payload.challenge)
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Phiên xác thực đã hết hạn. Vui lòng đăng nhập lại.")

    code = payload.code.strip()
    ok = (two_factor.consume_recovery_code(user_id, code) if "-" in code
          else two_factor.verify_code(user_id, code))
    if not ok:
        register_failed_login(ip, payload.challenge[:64])
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Mã không đúng hoặc đã được dùng.")

    reset_login_attempts(ip, payload.challenge[:64])
    user = _fetch_user_by_id(user_id)
    if not user or not user.get("is_active", True):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="Tài khoản không còn hoạt động.")

    _issue_session(response, request, user)
    return _public_user(user)


@router.get("/my-notice")
def my_notice(current_user: dict = Depends(get_current_user)):
    """Pending admin notice (warning) for the logged-in user, if any."""
    from app import activity

    return {"warning": activity.get_user_warning(current_user["id"])}


@router.post("/my-notice/ack")
def ack_my_notice(current_user: dict = Depends(get_current_user)):
    """Dismiss the pending warning after the user has read it."""
    from app import activity

    activity.ack_user_warning(current_user["id"])
    return {"status": "ok"}


@router.post("/refresh", response_model=UserOut)
def refresh(request: Request, response: Response):
    """Rotate the refresh cookie and mint a new short-lived access cookie.

    The SPA calls this transparently when an API request 401s on an expired
    access token. A missing/expired/revoked refresh token clears the cookies so
    the client falls back to the login screen.
    """
    result = rotate_refresh_token(request.cookies.get(REFRESH_COOKIE) or "")
    if not result:
        clear_auth_cookies(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired session",
        )
    user, new_refresh, fam = result
    set_auth_cookies(
        response,
        access_token=_access_for(user, fam),
        refresh_token=new_refresh,
        csrf_token=generate_csrf_token(),
        request=request,
    )
    return user


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, response: Response):
    """Revoke the refresh token server-side and clear all auth cookies.

    Ba việc, và việc thứ ba mới hoàn thành lời hứa của nút bấm: refresh token bị
    thu hồi, cookie bị xoá khỏi trình duyệt, và **access token của chính phiên
    này** bị đưa vào danh sách chặn.

    Thiếu việc thứ ba, "Đăng xuất" chỉ có nghĩa là "quên token đi" — bản thân
    token đã bị chụp lại ở đâu đó (nhật ký, proxy, tiện ích mở rộng, máy dùng
    chung) vẫn còn dùng được tới 60 phút sau khi người dùng tưởng mình đã ra.

    Chặn theo `jti` chứ không gọi `force_logout_user`: hàm kia đá MỌI thiết bị,
    nên đăng xuất trên điện thoại sẽ làm văng phiên trên máy tính.
    """
    from app.auth import deny_this_access_token
    from app.cookie_auth import ACCESS_COOKIE

    revoke_refresh_token(request.cookies.get(REFRESH_COOKIE) or "")
    deny_this_access_token(request.cookies.get(ACCESS_COOKIE) or "")
    clear_auth_cookies(response)
    return {"message": "Đã đăng xuất."}


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


class UpdateProfileRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=100)


@router.patch("/me")
def update_me(
    payload: UpdateProfileRequest,
    request: Request,
    current_user=Depends(get_current_user),
):
    """Đổi tên tài khoản, và kéo theo mọi bản sao của cái tên đó.

    Vì sao không phải một câu `UPDATE users SET username`: cái tên được CHÉP vào
    dữ liệu ngay lúc ghi — `samples.user_id`, `samples.username`,
    `raw_uploads.*`, `signers.display_name`, và cột `user_id` trong
    `dataset/samples.csv`. Đổi mỗi bảng `users` thì tài khoản mang tên mới còn
    3.860 mẫu đã đóng góp vẫn mang tên cũ, và người dùng mở Thùng rác của mình
    ra thấy tên người khác.

    `app/account_rename.py` giữ danh sách chỗ nào phải đổi và — quan trọng hơn —
    chỗ nào TUYỆT ĐỐI không được đổi: `audit_log.actor_label` và
    `legal_document_events.actor_label` là bằng chứng lịch sử, sửa chúng theo
    tên mới là viết lại lịch sử.
    """
    from app import audit
    from app.account_rename import RenameError, rename_user

    try:
        result = rename_user(str(current_user["id"]), payload.username)
    except RenameError as exc:
        raise HTTPException(status_code=exc.status_code,
                            detail={"code": exc.code, "message": str(exc)}) from None

    if result["changed"]:
        # Đổi tên chạm hàng nghìn dòng dữ liệu sản xuất. Nó thuộc đúng loại thao
        # tác mà sổ kiểm toán tồn tại để ghi lại.
        audit.record(
            "account.username.change",
            actor=current_user,
            target_type="user",
            target_id=str(current_user["id"]),
            detail={"old_username": result["old_username"],
                    "new_username": result["new_username"],
                    "rows": result["rows"]},
            request=request,
        )
    return result


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    request: Request,
):
    # Throttle per IP so nobody can spam reset emails / probe accounts.
    enforce_ip_limit(request, "forgot", max_calls=5, window=3600)
    result = request_password_reset(payload.identifier.strip())
    if result:
        user, token = result
        # Built from THIS request's host when that host is allowlisted, so a
        # moved tunnel URL mails a working link without a redeploy; otherwise
        # (or on a forged Host) it falls back to FRONTEND_BASE_URL.
        reset_link = f"{resolve_frontend_base_url(request)}/reset-password?token={token}"
        background_tasks.add_task(
            send_password_reset_email, user["email"], user["username"], reset_link
        )

    # Always the same response, whether or not the account exists.
    return {"message": _FORGOT_PASSWORD_GENERIC_MESSAGE}


@router.post("/reset-password", response_model=MessageResponse)
def reset_password(payload: ResetPasswordRequest, request: Request):
    # Throttle token-guessing attempts per IP.
    enforce_ip_limit(request, "reset", max_calls=10, window=3600)
    reset_password_with_token(payload.token, payload.new_password)
    return {"message": "Mật khẩu đã được đặt lại thành công. Vui lòng đăng nhập lại."}


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)
    #: Mã yếu tố thứ hai. Chỉ bắt buộc khi tài khoản ĐÃ bật 2FA. Nhận cả mã
    #: TOTP 6 chữ số lẫn mã khôi phục `xxxxx-xxxxx`, nên độ dài phải nới ra.
    code: Optional[str] = Field(None, max_length=32)


@router.post("/change-password", response_model=MessageResponse)
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    current_user=Depends(get_current_user),
):
    """Đổi mật khẩu khi ĐANG đăng nhập.

    Vì sao đường này phải tồn tại
    ------------------------------
    Trước 16/08/2026 chỉ có luồng quên-mật-khẩu qua email. Trang
    `/settings/security` có một khối chữ tên "Quên mật khẩu?" nhưng **không có
    nút nào** — người muốn đổi mật khẩu định kỳ phải giả vờ quên nó, chờ thư,
    rồi bấm liên kết. Với người dùng khiếm thính/khiếm ngôn mà dự án này phục
    vụ, mỗi bước thừa là một chỗ bỏ cuộc.

    Ba lớp, và vì sao đúng ba
    --------------------------
    1. **Mật khẩu hiện tại.** Không có nó thì một máy đang mở màn hình là đủ để
       chiếm vĩnh viễn tài khoản — lớp bảo vệ chỉ chặn kẻ ở xa, không chặn kẻ
       ngồi cạnh. Cùng lập luận với `two_factor._require_password`.
    2. **Yếu tố thứ hai, CHỈ KHI đã bật.** Bắt buộc bật 2FA mới cho đổi mật khẩu
       sẽ tạo một đường khoá cửa: người không có điện thoại thông minh sẽ không
       bao giờ đổi được mật khẩu. Đó là hướng hỏng tệ hơn thứ nó định chặn.
    3. **Mã khôi phục thay được mã TOTP.** Mất điện thoại không được đồng nghĩa
       với mất tài khoản. `consume_recovery_code` tiêu mã một lần — nên một mã
       bị nhìn trộm qua vai chỉ dùng được đúng một lần, và lần đó để lại dấu.

    Thu hồi MỌI phiên, kể cả phiên đang gọi
    ----------------------------------------
    `_apply_password_reset` đặt `sessions_invalid_before = NOW()`, nên người
    dùng phải đăng nhập lại. Nghe phiền, nhưng lý do phổ biến nhất để đổi mật
    khẩu là "tôi nghi có người vào được tài khoản" — giữ lại các phiên cũ là bỏ
    sót đúng cái mình định đuổi. Giao diện phải nói trước điều này.
    """
    from app import activity, audit, two_factor
    from app.auth import _apply_password_reset, _identity_cursor

    # Chặn dò mật khẩu bằng cách gọi thẳng endpoint này với một access token đã
    # chiếm được. Cùng ngưỡng với `/reset-password`.
    enforce_ip_limit(request, "change-password", max_calls=10, window=3600)

    if not verify_password(payload.current_password,
                           current_user.get("password_hash") or ""):
        activity.log_security_event(
            "password.change_rejected", actor=current_user.get("username", ""),
            target=str(current_user["id"]), actor_user=current_user, request=request)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Mật khẩu hiện tại không đúng.")

    if payload.new_password == payload.current_password:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Mật khẩu mới phải khác mật khẩu hiện tại.")

    used_recovery = False
    if two_factor.is_enabled(current_user["id"]):
        code = (payload.code or "").strip()
        if not code:
            # 400 kèm mã máy đọc được, để giao diện hiện ô nhập mã thay vì hiện
            # một câu lỗi đỏ mà người dùng không biết phải làm gì với nó.
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "2fa_required",
                        "message": "Tài khoản đang bật xác thực hai bước. "
                                   "Nhập mã 6 chữ số hoặc một mã khôi phục."})
        if not two_factor.verify_code(current_user["id"], code):
            used_recovery = two_factor.consume_recovery_code(current_user["id"], code)
            if not used_recovery:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                    detail="Mã xác thực không đúng.")

    with _identity_cursor() as cur:
        _apply_password_reset(cur, str(current_user["id"]), payload.new_password)

    audit.record(
        "account.password.change", actor=current_user, target_type="user",
        target_id=str(current_user["id"]),
        detail={"used_recovery_code": used_recovery}, request=request)
    activity.log_security_event(
        "password.changed", actor=current_user.get("username", ""),
        target=str(current_user["id"]), actor_user=current_user, request=request)

    return {"message": "Đã đổi mật khẩu. Mọi thiết bị đã bị đăng xuất, "
                       "vui lòng đăng nhập lại."}


# --------------------------------------------------------------- đổi email
#
# Hai bước, và cả hai đều bắt buộc:
#
#   start    -> mật khẩu + địa chỉ mới  ->  gửi mã 6 chữ số TỚI ĐỊA CHỈ MỚI
#   confirm  -> mật khẩu + mã           ->  đổi `users.email`
#
# **Mã đi tới địa chỉ MỚI, không phải địa chỉ cũ.** Đó là toàn bộ điểm: thứ cần
# chứng minh là "bạn đọc được hộp thư mới", chứ không phải "bạn đọc được hộp thư
# cũ" — cái sau đã được chứng minh bằng việc đang đăng nhập.
#
# **Mật khẩu hỏi ở CẢ HAI bước.** Nghe thừa, nhưng bước `start` một mình chỉ gửi
# một lá thư; bước `confirm` mới là bước đổi địa chỉ nhận thư khôi phục tài
# khoản — tức là bước có thể biến một phiên bị chiếm thành mất tài khoản vĩnh
# viễn. Một cửa sổ trình duyệt bỏ quên giữa hai bước không được phép là đủ.
#
# Vì sao dùng lại `purpose='verify_email'` thay vì thêm `change_email`
# --------------------------------------------------------------------
# `verification_codes.purpose` có ràng buộc CHECK ở lược đồ, nên một mục đích
# mới là một bước migration MỘT CHIỀU trên cơ sở dữ liệu sản xuất. Không đáng,
# vì mục đích ở đây trùng khớp: cả hai đều là "chứng minh bạn kiểm soát địa chỉ
# này". Khác biệt duy nhất là hệ quả, và hệ quả do endpoint quyết chứ không do
# hàng dữ liệu quyết.
#
# Điều đó an toàn vì `otp.mark_verified` chỉ đánh dấu khi địa chỉ TRÙNG email
# hiện tại (`AND lower(email) = %s`). Nên nếu ai đó xác nhận mã này qua endpoint
# chung `/verify/confirm`, câu UPDATE khớp 0 dòng và **không có gì xảy ra** —
# không đổi email, không đánh dấu nhầm.


class ChangeEmailStartRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    # `str` + `regex`, KHÔNG phải `EmailStr`: `EmailStr` kéo theo gói
    # `email_validator` chưa có trong ảnh, và cả `RegisterRequest` cũng dùng
    # `str`. Thêm một phụ thuộc cho đúng một trường là đổi hình dạng bản dựng để
    # lấy một phép kiểm mà `otp.normalize_destination` đằng nào cũng làm lại.
    #
    # **`regex=`, không phải `pattern=`.** Dự án chạy Pydantic 1.10, và ở v1 một
    # tham số `Field` không nhận ra được **bỏ qua trong im lặng** — không cảnh
    # báo, không lỗi, chỉ là phép kiểm không bao giờ chạy. Bản đầu viết
    # `pattern=` (tên của v2) và mọi chuỗi rác đều đi lọt. Bài
    # `test_dia_chi_khong_hop_le_bi_chan_o_lop_kieu` tồn tại đúng để bắt cái
    # im lặng ấy — nếu một ngày nâng lên Pydantic v2, nó sẽ đỏ và nhắc đổi lại
    # thành `pattern=`.
    new_email: str = Field(..., min_length=3, max_length=255,
                           regex=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ChangeEmailConfirmRequest(BaseModel):
    current_password: str = Field(..., min_length=1, max_length=128)
    code: str = Field(..., min_length=4, max_length=10)


#: Hai lớp phản hồi dưới đây KHÔNG phải thủ tục thừa.
#:
#: `test_login_response_shape.py` canh mọi đường trong router này: thiếu
#: `response_model` là đỏ, trừ khi có lý do ghi trong danh sách miễn trừ. Lý do
#: của cổng ấy rất cụ thể — bỏ `response_model=UserOut` khỏi `/auth/login` để
#: trả được hai hình dạng đã vô tình gỡ luôn bộ lọc duy nhất ngăn
#: `password_hash` đi ra ngoài.
#:
#: Hai đường đổi email không chạm hồ sơ người dùng, nhưng "không chạm" là điều
#: đúng HÔM NAY. Khai kiểu tường minh làm nó đúng cả ngày mai, và rẻ hơn nhiều
#: so với một dòng miễn trừ mà người sửa sau phải tin.
class ChangeEmailStartResponse(BaseModel):
    challenge_id: str
    sent_to: str
    expires_in_minutes: int


class ChangeEmailConfirmResponse(BaseModel):
    email: str
    email_verified: bool


def _guard_email_change(current_user, password: str, request: Request) -> None:
    from app import activity

    enforce_ip_limit(request, "change-email", max_calls=10, window=3600)
    if not verify_password(password, current_user.get("password_hash") or ""):
        activity.log_security_event(
            "email.change_rejected", actor=current_user.get("username", ""),
            target=str(current_user["id"]), actor_user=current_user, request=request)
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Mật khẩu hiện tại không đúng.")


@router.post("/change-email/start", response_model=ChangeEmailStartResponse)
def change_email_start(
    payload: ChangeEmailStartRequest,
    request: Request,
    current_user=Depends(get_current_user),
):
    from app import otp
    from app.auth import _identity_cursor
    from app.email_service import EmailNotConfigured, send_verification_code_email

    _guard_email_change(current_user, payload.current_password, request)

    new_email = str(payload.new_email).strip().lower()
    if new_email == str(current_user.get("email") or "").strip().lower():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail="Địa chỉ mới trùng địa chỉ đang dùng.")

    # Kiểm trùng ở mặt phẳng DANH TÍNH, không phải trong tenant: `users.email` là
    # khoá đăng nhập của cả nền tảng, nên "chưa ai dùng" phải đúng trên toàn hệ
    # thống. Hỏi trong phạm vi tenant sẽ báo "chưa ai dùng" cho một địa chỉ đang
    # thuộc tổ chức khác, rồi câu INSERT vỡ vì ràng buộc UNIQUE — một lỗi 500 ở
    # bước cuối thay vì một câu trả lời rõ ràng ở bước đầu.
    with _identity_cursor() as cur:
        cur.execute("SELECT 1 FROM users WHERE lower(email) = %s AND id <> %s",
                    (new_email, str(current_user["id"])))
        if cur.fetchone():
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail="Địa chỉ này đã có tài khoản khác dùng.")

    try:
        challenge_id, code = otp.issue(
            user_id=current_user["id"], purpose="verify_email",
            channel="email", destination=new_email)
    except otp.OtpError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    try:
        send_verification_code_email(new_email, code, "verify_email")
    except EmailNotConfigured as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return {"challenge_id": challenge_id, "sent_to": new_email,
            "expires_in_minutes": settings.otp_ttl_minutes}


@router.post("/change-email/confirm", response_model=ChangeEmailConfirmResponse)
def change_email_confirm(
    payload: ChangeEmailConfirmRequest,
    request: Request,
    current_user=Depends(get_current_user),
):
    from app import activity, audit, notifications, otp
    from app.auth import _identity_cursor

    _guard_email_change(current_user, payload.current_password, request)

    try:
        result = otp.verify(user_id=current_user["id"], purpose="verify_email",
                            code=payload.code)
    except otp.OtpError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    new_email = str(result["destination"]).strip().lower()
    old_email = str(current_user.get("email") or "")

    # Chỉ MỘT câu UPDATE, và đó là câu đúng — khác hẳn đổi tên đăng nhập.
    #
    # `rename_user` phải chạm vào năm bảng cộng `samples.csv` vì cái TÊN được
    # chép vào dữ liệu ngay lúc ghi. Địa chỉ email thì không: cả lược đồ chỉ có
    # hai cột mang email, `users.email` và `tenant_invitations.email`.
    #
    # Và cột thứ hai **cố ý không đổi theo**. Nó ghi lại địa chỉ mà lời mời đã
    # được gửi TỚI — một sự kiện đã xảy ra, không phải một thuộc tính hiện tại
    # của tài khoản. Viết lại nó theo địa chỉ mới là sửa lịch sử, cùng lý do
    # `audit_log.actor_label` giữ nguyên tên cũ sau khi đổi tên đăng nhập.
    with _identity_cursor() as cur:
        cur.execute(
            "UPDATE users SET email = %s, email_verified_at = NOW() WHERE id = %s",
            (new_email, str(current_user["id"])))

    # Báo cho chính chủ, và ghi cả hai nhật ký. Đổi địa chỉ nhận thư khôi phục
    # là thao tác biến một phiên bị chiếm thành mất tài khoản vĩnh viễn — nếu
    # chủ tài khoản không bao giờ biết, họ không có gì để tố cáo.
    notifications.notify(
        str(current_user["id"]), "security", "Địa chỉ email đã được đổi",
        body=f"Từ {old_email} sang {new_email}.",
        link="/settings/security", severity="critical")
    audit.record("account.email.change", actor=current_user, target_type="user",
                 target_id=str(current_user["id"]),
                 detail={"old_email": old_email, "new_email": new_email},
                 request=request)
    activity.log_security_event(
        "email.changed", actor=current_user.get("username", ""),
        target=str(current_user["id"]), actor_user=current_user, request=request)

    return {"email": new_email, "email_verified": True}