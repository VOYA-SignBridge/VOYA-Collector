"""Password hashing primitives for the identity bounded context."""

from passlib.context import CryptContext


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Equalizes authentication cost for missing and existing accounts so callers
# cannot use response timing to enumerate usernames.
DUMMY_PASSWORD_HASH = pwd_context.hash(
    "voya-timing-equalizer-not-a-real-secret"
)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    if not plain_password or not hashed_password:
        return False
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        return False
