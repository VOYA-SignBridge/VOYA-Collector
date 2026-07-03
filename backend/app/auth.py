from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.config import settings
from app.storage.postgres_connection import connect_postgres

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)


def _get_conn():
    return connect_postgres(connect_timeout=5)


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
        "role": row.get("role_name"),
        "created_at": row.get("created_at"),
        "profile": {
            "full_name": row.get("full_name") or "",
            "avatar_url": row.get("avatar_url") or "",
            "yob": row.get("yob"),
            "gender": row.get("gender")
        }
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
    return payload


def _fetch_user_by_id(user_id: str) -> Optional[Dict[str, Any]]:
    conn = _get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT u.id, u.username, u.email, u.password_hash, u.is_active, u.is_admin, u.created_at,
                           r.name as role_name,
                           p.full_name, p.avatar_url, p.yob, p.gender
                    FROM users u
                    LEFT JOIN roles r ON u.role_id = r.id
                    LEFT JOIN user_profiles p ON u.id = p.user_id
                    WHERE u.id = %s AND u.deleted_at IS NULL
                    """,
                    (user_id,),
                )
                row = cur.fetchone()
                return _row_to_user(row)
    finally:
        conn.close()


def _fetch_user_by_login(identifier: str) -> Optional[Dict[str, Any]]:
    login = _normalize_login(identifier)
    if not login:
        return None

    conn = _get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT u.id, u.username, u.email, u.password_hash, u.is_active, u.is_admin, u.created_at,
                           r.name as role_name,
                           p.full_name, p.avatar_url, p.yob, p.gender
                    FROM users u
                    LEFT JOIN roles r ON u.role_id = r.id
                    LEFT JOIN user_profiles p ON u.id = p.user_id
                    WHERE (lower(u.username) = %s OR lower(u.email) = %s) AND u.deleted_at IS NULL
                    LIMIT 1
                    """,
                    (login, login),
                )
                row = cur.fetchone()
                return _row_to_user(row)
    finally:
        conn.close()


def create_user(
    username: str,
    email: str,
    password: str,
    is_admin: bool = False,
) -> Dict[str, Any]:
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

    conn = _get_conn()
    try:
        with conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    INSERT INTO users (id, username, email, password_hash, is_active, is_admin)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id, username, email, password_hash, is_active, is_admin, created_at
                    """,
                    (
                        user_id,
                        username_norm,
                        email_norm,
                        password_hash,
                        True,
                        bool(is_admin),
                    ),
                )
                row = cur.fetchone()
                return _row_to_user(row) or {}
    finally:
        conn.close()


def authenticate_user(identifier: str, password: str) -> Optional[Dict[str, Any]]:
    user = _fetch_user_by_login(identifier)
    if not user:
        return None
    if not user.get("is_active", True):
        return None
    if not verify_password(password, user["password_hash"]):
        return None
    return user


def get_current_user_optional(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Optional[Dict[str, Any]]:
    if credentials is None:
        return None

    payload = _decode_token(credentials.credentials)
    user_id = str(payload.get("sub") or "")
    user = _fetch_user_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> Dict[str, Any]:
    user = get_current_user_optional(credentials)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return user


def require_admin(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
    if not current_user.get("is_admin", False) and current_user.get("role") != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


def require_role(allowed_roles: list[str]):
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)):
        user_role = current_user.get("role")
        if user_role not in allowed_roles and not current_user.get("is_admin", False):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Require one of roles: {allowed_roles}"
            )
        return current_user
    return role_checker