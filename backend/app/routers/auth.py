from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, Response, status, Depends  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel, Field  # pyright: ignore[reportMissingImports]

from app.config import settings
from app.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    create_user,
    get_current_user,
    request_password_reset,
    reset_password_with_token,
    revoke_refresh_token,
    rotate_refresh_token,
)
from app.cookie_auth import (
    REFRESH_COOKIE,
    clear_auth_cookies,
    generate_csrf_token,
    set_auth_cookies,
)
from app.rate_limit import (
    check_login_allowed,
    client_ip,
    enforce_ip_limit,
    register_failed_login,
    reset_login_attempts,
)
from app.email_service import send_password_reset_email

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


class MessageResponse(BaseModel):
    message: str


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest, request: Request):
    # Throttle account creation per IP to stop mass-registration spam.
    enforce_ip_limit(request, "register", max_calls=10, window=3600)
    user = create_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        is_admin=False,
    )
    return user


def _access_for(user: dict) -> str:
    return create_access_token(
        data={
            "sub": user["id"],
            "username": user["username"],
            "email": user["email"],
            "is_admin": user["is_admin"],
        },
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )


@router.post("/login", response_model=UserOut)
def login(payload: LoginRequest, request: Request, response: Response):
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
    set_auth_cookies(
        response,
        access_token=_access_for(user),
        refresh_token=create_refresh_token(user["id"]),
        csrf_token=generate_csrf_token(),
    )
    return user


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
    user, new_refresh = result
    set_auth_cookies(
        response,
        access_token=_access_for(user),
        refresh_token=new_refresh,
        csrf_token=generate_csrf_token(),
    )
    return user


@router.post("/logout", response_model=MessageResponse)
def logout(request: Request, response: Response):
    """Revoke the refresh token server-side and clear all auth cookies."""
    revoke_refresh_token(request.cookies.get(REFRESH_COOKIE) or "")
    clear_auth_cookies(response)
    return {"message": "Đã đăng xuất."}


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


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
        reset_link = f"{settings.frontend_base_url.rstrip('/')}/reset-password?token={token}"
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