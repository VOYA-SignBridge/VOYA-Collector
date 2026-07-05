from datetime import datetime, timedelta
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, HTTPException, status, Depends  # pyright: ignore[reportMissingImports]
from pydantic import BaseModel, Field  # pyright: ignore[reportMissingImports]

from app.config import settings
from app.auth import (
    authenticate_user,
    create_access_token,
    create_user,
    get_current_user,
    request_password_reset,
    reset_password_with_token,
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


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(payload: RegisterRequest):
    user = create_user(
        username=payload.username,
        email=payload.email,
        password=payload.password,
        is_admin=False,
    )
    return user


@router.post("/login", response_model=TokenOut)
def login(payload: LoginRequest):
    user = authenticate_user(payload.identifier, payload.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username/email or password",
        )

    token = create_access_token(
        data={
            "sub": user["id"],
            "username": user["username"],
            "email": user["email"],
            "is_admin": user["is_admin"],
        },
        expires_delta=timedelta(minutes=settings.access_token_expire_minutes),
    )
    return {
        "access_token": token,
        "token_type": "bearer",
        "user": user,
    }


@router.get("/me", response_model=UserOut)
def me(current_user=Depends(get_current_user)):
    return current_user


class ForgotPasswordRequest(BaseModel):
    identifier: str = Field(..., min_length=1, max_length=255)


class MessageResponse(BaseModel):
    message: str


class ResetPasswordRequest(BaseModel):
    token: str = Field(..., min_length=1)
    new_password: str = Field(..., min_length=8, max_length=128)


@router.post("/forgot-password", response_model=MessageResponse)
def forgot_password(payload: ForgotPasswordRequest, background_tasks: BackgroundTasks):
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
def reset_password(payload: ResetPasswordRequest):
    reset_password_with_token(payload.token, payload.new_password)
    return {"message": "Mật khẩu đã được đặt lại thành công. Vui lòng đăng nhập lại."}