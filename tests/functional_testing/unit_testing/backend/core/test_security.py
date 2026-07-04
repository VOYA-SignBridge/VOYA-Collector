"""Unit tests — crypto primitives (core/security.py, GĐ 1 §7.5)."""
import uuid
from datetime import timedelta

import pytest
from jose import JWTError

from app.core import security


class TestPasswords:
    def test_hash_roundtrip(self):
        h = security.hash_password("S3cret!123")
        assert h != "S3cret!123"
        assert security.verify_password("S3cret!123", h)
        assert not security.verify_password("wrong", h)


class TestAccessToken:
    def test_roundtrip_claims(self):
        token = security.create_access_token({"sub": "user-1", "username": "minh"})
        claims = security.decode_access_token(token)
        assert claims["sub"] == "user-1"
        assert claims["username"] == "minh"
        assert "exp" in claims and "jti" in claims

    def test_expired_token_is_rejected(self):
        token = security.create_access_token(
            {"sub": "user-1"}, expires_delta=timedelta(seconds=-10)
        )
        with pytest.raises(JWTError):
            security.decode_access_token(token)
        assert security.try_decode_access_token(token) is None

    def test_tampered_token_is_rejected(self):
        token = security.create_access_token({"sub": "user-1"})
        header, payload, sig = token.split(".")
        forged = f"{header}.{payload}.{'A' * len(sig)}"
        assert security.try_decode_access_token(forged) is None


class TestRefreshToken:
    def test_opaque_token_and_stable_hash(self):
        t = security.generate_refresh_token()
        assert len(t) >= 48
        h1, h2 = security.hash_refresh_token(t), security.hash_refresh_token(t)
        assert h1 == h2 and len(h1) == 64  # sha256 hex — fits column String(64)

    def test_two_tokens_never_collide(self):
        assert security.generate_refresh_token() != security.generate_refresh_token()


class TestUserRef:
    """Pseudonymous id exported to Sheets/CSV (§11.3 erd_v2)."""

    def test_stable_and_12_hex_chars(self):
        uid = uuid.uuid4()
        ref1, ref2 = security.make_user_ref(uid), security.make_user_ref(uid)
        assert ref1 == ref2
        assert len(ref1) == 12
        int(ref1, 16)  # must be hex

    def test_different_users_get_different_refs(self):
        assert security.make_user_ref(uuid.uuid4()) != security.make_user_ref(
            uuid.uuid4()
        )
