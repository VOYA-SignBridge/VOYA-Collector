"""SOT crypto — Ed25519 keygen/sign/verify + authorized-key registry.

These are the security core (the "only registered machines can write" boundary),
so coverage is deliberately exhaustive: happy paths, every tamper variant, and
the registry's duplicate/again guards.
"""

from __future__ import annotations

from datetime import date

import pytest

from app.sot import keys


# ---------------------------------------------------------------------------
# Keypair (de)serialization
# ---------------------------------------------------------------------------

def test_private_key_b64_roundtrip():
    pk = keys.generate_private_key()
    b64 = keys.private_key_to_b64(pk)
    restored = keys.private_key_from_b64(b64)
    # Same private key => same public key.
    assert keys.public_key_b64(restored) == keys.public_key_b64(pk)


def test_two_keys_are_distinct():
    a = keys.public_key_b64(keys.generate_private_key())
    b = keys.public_key_b64(keys.generate_private_key())
    assert a != b


def test_fingerprint_is_deterministic_and_key_specific():
    pk = keys.generate_private_key()
    pub = keys.public_key_b64(pk)
    assert keys.fingerprint(pub) == keys.fingerprint(pub)
    other = keys.public_key_b64(keys.generate_private_key())
    assert keys.fingerprint(pub) != keys.fingerprint(other)
    assert len(keys.fingerprint(pub)) == 16


# ---------------------------------------------------------------------------
# Sign / verify
# ---------------------------------------------------------------------------

def test_sign_then_verify_ok():
    pk = keys.generate_private_key()
    pub = keys.public_key_b64(pk)
    data = b"the truth"
    sig = keys.sign(pk, data)
    assert keys.verify(pub, data, sig) is True


def test_verify_fails_on_tampered_data():
    pk = keys.generate_private_key()
    pub = keys.public_key_b64(pk)
    sig = keys.sign(pk, b"original")
    assert keys.verify(pub, b"original ", sig) is False  # trailing space
    assert keys.verify(pub, b"modified", sig) is False


def test_verify_fails_with_wrong_public_key():
    pk = keys.generate_private_key()
    other_pub = keys.public_key_b64(keys.generate_private_key())
    sig = keys.sign(pk, b"data")
    assert keys.verify(other_pub, b"data", sig) is False


def test_verify_fails_on_garbage_signature():
    pub = keys.public_key_b64(keys.generate_private_key())
    assert keys.verify(pub, b"data", "not-base64-!!") is False
    assert keys.verify(pub, b"data", "") is False
    assert keys.verify("bad-key", b"data", "AAAA") is False


# ---------------------------------------------------------------------------
# Private key file I/O
# ---------------------------------------------------------------------------

def test_save_and_load_private_key(tmp_path):
    pk = keys.generate_private_key()
    path = tmp_path / "priv.key"
    keys.save_private_key(pk, path)
    loaded = keys.load_private_key(path)
    assert keys.public_key_b64(loaded) == keys.public_key_b64(pk)


def test_save_refuses_overwrite_unless_force(tmp_path):
    path = tmp_path / "priv.key"
    keys.save_private_key(keys.generate_private_key(), path)
    with pytest.raises(FileExistsError):
        keys.save_private_key(keys.generate_private_key(), path)
    # force overwrites
    new_pk = keys.generate_private_key()
    keys.save_private_key(new_pk, path, force=True)
    assert keys.public_key_b64(keys.load_private_key(path)) == keys.public_key_b64(new_pk)


def test_load_missing_key_raises_helpful_error(tmp_path):
    with pytest.raises(FileNotFoundError) as exc:
        keys.load_private_key(tmp_path / "nope.key")
    assert "not registered" in str(exc.value).lower()


# ---------------------------------------------------------------------------
# Authorized-key registry
# ---------------------------------------------------------------------------

def _authz(tmp_path):
    p = tmp_path / "authorized_keys.json"
    p.write_text("[]", encoding="utf-8")
    return p


def test_load_authorized_keys_empty(tmp_path):
    assert keys.load_authorized_keys(_authz(tmp_path)) == []
    assert keys.load_authorized_keys(tmp_path / "missing.json") == []


def test_add_authorized_key_appends_entry(tmp_path):
    path = _authz(tmp_path)
    pub = keys.public_key_b64(keys.generate_private_key())
    result = keys.add_authorized_key("desktop-A", pub, path, today=date(2026, 7, 18))
    assert len(result) == 1
    entry = result[0]
    assert entry["name"] == "desktop-A"
    assert entry["public_key"] == pub
    assert entry["added_at"] == "2026-07-18"
    assert entry["fingerprint"] == keys.fingerprint(pub)
    # persisted
    assert keys.load_authorized_keys(path)[0]["public_key"] == pub


def test_add_rejects_duplicate_public_key(tmp_path):
    path = _authz(tmp_path)
    pub = keys.public_key_b64(keys.generate_private_key())
    keys.add_authorized_key("desktop-A", pub, path)
    with pytest.raises(ValueError, match="already registered"):
        keys.add_authorized_key("desktop-A-again", pub, path)


def test_add_rejects_duplicate_name_with_different_key(tmp_path):
    path = _authz(tmp_path)
    keys.add_authorized_key("laptop", keys.public_key_b64(keys.generate_private_key()), path)
    with pytest.raises(ValueError, match="already used"):
        keys.add_authorized_key("laptop", keys.public_key_b64(keys.generate_private_key()), path)


def test_verify_with_authorized_returns_matching_name(tmp_path):
    path = _authz(tmp_path)
    pk1 = keys.generate_private_key()
    pk2 = keys.generate_private_key()
    keys.add_authorized_key("laptop-1", keys.public_key_b64(pk1), path)
    keys.add_authorized_key("laptop-2", keys.public_key_b64(pk2), path)
    authorized = keys.load_authorized_keys(path)

    data = b"payload"
    # Signed by laptop-2 -> accepted, name reported.
    assert keys.verify_with_authorized(data, keys.sign(pk2, data), authorized) == "laptop-2"
    assert keys.verify_with_authorized(data, keys.sign(pk1, data), authorized) == "laptop-1"


def test_verify_with_authorized_rejects_unregistered_signer(tmp_path):
    path = _authz(tmp_path)
    keys.add_authorized_key("laptop-1", keys.public_key_b64(keys.generate_private_key()), path)
    authorized = keys.load_authorized_keys(path)

    rogue = keys.generate_private_key()
    data = b"payload"
    # Signed by a key NOT in the allowlist -> None (reject).
    assert keys.verify_with_authorized(data, keys.sign(rogue, data), authorized) is None


def test_revocation_removes_ability_to_verify(tmp_path):
    """Removing a key from the allowlist (revocation) makes its sigs rejected."""
    path = _authz(tmp_path)
    pk = keys.generate_private_key()
    keys.add_authorized_key("old-laptop", keys.public_key_b64(pk), path)
    data = b"x"
    sig = keys.sign(pk, data)
    assert keys.verify_with_authorized(data, sig, keys.load_authorized_keys(path)) == "old-laptop"

    # Revoke: empty the allowlist.
    path.write_text("[]", encoding="utf-8")
    assert keys.verify_with_authorized(data, sig, keys.load_authorized_keys(path)) is None
