"""Crypto primitives for the v2 stack (Refactore task 2.2; Architecture §1.7).

- Access token: short-lived JWT (RAM-only on the client).
- Refresh token: opaque random string; only its SHA-256 hash is stored
  (USER_SESSIONS.refresh_token_hash) — DB leak reveals nothing.
- user_ref: peppered pseudonymous id exported to Sheets/CSV (§11.3).
"""
from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import get_settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


# ── Passwords ──────────────────────────────────────────────────────
def hash_password(plain: str) -> str:
    return pwd_context.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


# ── Access token (JWT) ─────────────────────────────────────────────
def create_access_token(
    data: Dict[str, Any], expires_delta: Optional[timedelta] = None
) -> str:
    settings = get_settings()
    to_encode = dict(data)
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.access_token_expire_minutes)
    )
    to_encode.update({"exp": expire, "jti": uuid.uuid4().hex})
    return jwt.encode(
        to_encode, settings.jwt_secret_key, algorithm=settings.jwt_algorithm
    )


def decode_access_token(token: str) -> Dict[str, Any]:
    """Returns claims; raises ``jose.JWTError`` on any tamper/expiry."""
    settings = get_settings()
    return jwt.decode(
        token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
    )


def try_decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        return decode_access_token(token)
    except JWTError:
        return None


# ── Refresh token (opaque + hashed at rest) ────────────────────────
def generate_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


# ── Pseudonymous user_ref (§11.3 erd_v2) ───────────────────────────
def make_user_ref(user_id: uuid.UUID | str) -> str:
    """`SHA-256(user_id ‖ PEPPER)[:12]` — stable, non-reversible without
    the server-side pepper (GDPR pseudonymization)."""
    settings = get_settings()
    digest = hashlib.sha256(
        f"{user_id}{settings.user_ref_pepper}".encode("utf-8")
    ).hexdigest()
    return digest[:12]
