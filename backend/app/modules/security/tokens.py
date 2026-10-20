"""Hashing secrets that are stored, and the one distinction that matters.

Two kinds of secret live in this database, and they need different treatment:

**High-entropy tokens** — invitation links, refresh tokens, password-reset
links. 32-48 random bytes. There is no dictionary to search, so a plain
SHA-256 of the token is enough: an attacker holding the whole table cannot
invert a single row in any amount of time that matters.

**Low-entropy codes** — the six-digit OTP a person types from an SMS. There are
exactly one million of them. A plain hash is *decoration*: an attacker who
reads the table builds the full table of one million digests in under a second
and reverses every outstanding code. These need HMAC keyed by a pepper that
lives OUTSIDE the database, so that reading the database is not enough.

Both are here, next to each other, with names that say which is which. The
alternative — one `hash_token()` helper — is how a six-digit code ends up
protected like a 256-bit one, and nothing about the call site looks wrong.

Neither the raw token nor the raw code is ever logged, returned in an error, or
put in a metric label. See `docs/01-architecture/TENANT_LIFECYCLE_AND_OTP.md` §"What is never
written down".
"""

from __future__ import annotations

import hashlib
import hmac
import logging
import secrets
from typing import Final

from app.config import settings

logger = logging.getLogger(__name__)

#: Bytes of entropy for a link token. 32 bytes -> 43 urlsafe chars.
LINK_TOKEN_BYTES: Final[int] = 32


class PepperMissingError(RuntimeError):
    """Raised when a low-entropy code is hashed with no pepper configured.

    Deliberately fatal rather than falling back to a plain hash. A silent
    downgrade here produces a system that looks identical from the outside and
    protects nothing — the exact failure mode this module exists to prevent.
    """


def new_link_token() -> str:
    """A fresh high-entropy token for an invitation or reset link."""
    return secrets.token_urlsafe(LINK_TOKEN_BYTES)


def hash_link_token(token: str) -> str:
    """Digest for a HIGH-entropy token. Plain SHA-256 is correct here.

    Matches what `auth.py` already does for refresh and reset tokens; changing
    those would invalidate every live session and reset link for no gain.
    """
    return hashlib.sha256((token or "").encode("utf-8")).hexdigest()


def _pepper() -> bytes:
    pepper = (settings.otp_pepper or "").strip()
    if not pepper:
        raise PepperMissingError(
            "OTP_PEPPER is not set. A six-digit code hashed without a pepper is "
            "reversible by anyone who can read the database, so this refuses "
            "rather than storing one. Generate 32+ random characters and set "
            "OTP_PEPPER in the environment."
        )
    return pepper.encode("utf-8")


def hash_code(code: str, *, purpose: str, subject: str) -> str:
    """Digest for a LOW-entropy code (OTP). HMAC keyed by an out-of-database pepper.

    `purpose` and `subject` are bound into the message, not for secrecy but for
    domain separation: a digest minted to verify a phone number must not also
    validate as a password-reset code for the same account, and the same code
    sent to two different addresses must not collide. Without this, one
    captured digest is reusable across every flow that happens to share the
    six digits.
    """
    message = f"{purpose}\x00{subject}\x00{code}".encode("utf-8")
    return hmac.new(_pepper(), message, hashlib.sha256).hexdigest()


def codes_match(candidate_hash: str, stored_hash: str) -> bool:
    """Constant-time comparison of two digests. Empty never matches.

    Both sides are hex digests of fixed length, so this leaks nothing about
    length; `compare_digest` removes the early-exit timing signal that would
    otherwise let an attacker learn a digest one character at a time.

    The emptiness check is not defensive clutter. `compare_digest("", "")` is
    True, so without it a row whose digest was never written — a challenge that
    does not exist — would be satisfied by a caller who also supplies nothing.
    That is the fail-open shape, reached by two absent values rather than by a
    wrong one, which is exactly the kind that survives review.
    """
    if not candidate_hash or not stored_hash:
        return False
    return hmac.compare_digest(candidate_hash, stored_hash)
